# UI and deps imported only when running the app
import os
import logging
import requests
import pandas as pd
import json
from sqlalchemy import create_engine
import psycopg2
from prometheus_client import Counter, Gauge, start_http_server
import threading

# Streamlit and altair imported only inside run_app to keep module import-safe
# PostgreSQL configuration (update with your credentials)
LOG_LEVEL = os.getenv('POKEMON_LOG_LEVEL', 'INFO')
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('pokemon')

# Read DB config from environment variables (secure) with sensible defaults where appropriate
db_config = {
    'user': os.getenv('POKEMON_DB_USER', 'neondb_owner'),
    'password': os.getenv('POKEMON_DB_PASSWORD', ''),
    'host': os.getenv('POKEMON_DB_HOST', 'localhost'),
    'port': os.getenv('POKEMON_DB_PORT', '5432'),
    'database': os.getenv('POKEMON_DB_NAME', 'pokemon_db')
}

if not db_config['password']:
    logger.warning('No DB password set in POKEMON_DB_PASSWORD environment variable; database connections may fail.')
# Create PostgreSQL database and table
def init_db():
    """Create table if not exists. Raises psycopg2.Error on failure."""
    conn = psycopg2.connect(**db_config)
    conn.set_session(autocommit=True)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pokemon (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            types TEXT,
            height FLOAT,
            weight FLOAT,
            hp INTEGER,
            attack INTEGER,
            defense INTEGER,
            special_attack INTEGER,
            special_defense INTEGER,
            speed INTEGER,
            stat_total INTEGER,
            abilities JSONB,
            evolution_chain_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.close()
    conn.close()

# Function to fetch list of Pokémon
def fetch_pokemon_list(limit=50):
    url = f"https://pokeapi.co/api/v2/pokemon?limit={limit}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['results']
    else:
        # Avoid UI calls from library functions; return empty list on failure
        logger.error("Failed to fetch Pokémon list. status=%s url=%s", response.status_code, url)
        return []

# Function to fetch details for a single Pokémon
def fetch_pokemon_details(url):
    """Fetch detailed Pokemon info. Returns dict with 'types' as list and other fields. Returns None on failure."""
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return None
    data = resp.json()
    types = [t['type']['name'] for t in data.get('types', [])]
    stats = {s['stat']['name']: s['base_stat'] for s in data.get('stats', [])}
    abilities = [a['ability']['name'] for a in data.get('abilities', [])]

    # Fetch evolution chain ID (best-effort)
    evolution_chain_id = None
    species_url = data.get('species', {}).get('url')
    if species_url:
        try:
            species_response = requests.get(species_url, timeout=10)
            if species_response.status_code == 200:
                species_data = species_response.json()
                evolution_url = species_data.get('evolution_chain', {}).get('url')
                if evolution_url:
                    # url like .../evolution-chain/67/
                    parts = [p for p in evolution_url.split('/') if p]
                    evolution_chain_id = int(parts[-1]) if parts and parts[-1].isdigit() else None
        except Exception:
            evolution_chain_id = None

    stat_total = sum([
        stats.get('hp', 0), stats.get('attack', 0), stats.get('defense', 0),
        stats.get('special-attack', 0), stats.get('special-defense', 0), stats.get('speed', 0)
    ])

    return {
        'name': data.get('name'),
        'types': types,
        'types_str': ', '.join(types),
        'height': data.get('height'),
        'weight': data.get('weight'),
        'hp': stats.get('hp', 0),
        'attack': stats.get('attack', 0),
        'defense': stats.get('defense', 0),
        'special_attack': stats.get('special-attack', 0),
        'special_defense': stats.get('special-defense', 0),
        'speed': stats.get('speed', 0),
        'stat_total': stat_total,
        'abilities': abilities,
        'evolution_chain_id': evolution_chain_id
    }

# Function to save DataFrame to PostgreSQL
def save_to_postgres(df):
    """Persist DataFrame to postgres. Serializes list fields to JSON/text before saving."""
    engine = create_engine(f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?sslmode=require")

    # Ensure abilities is JSON and types stored as string
    df = df.copy()
    if 'abilities' in df.columns:
        df['abilities'] = df['abilities'].apply(lambda a: json.dumps(a) if not pd.isna(a) else None)
    if 'types' in df.columns:
        df['types'] = df['types'].apply(lambda t: json.dumps(t) if not pd.isna(t) else None)
    if 'types_str' in df.columns:
        # keep a human-readable representation too
        df['types_str'] = df['types_str']

    logger.info('Saving %d rows to Postgres table pokemon', len(df))
    df.to_sql('pokemon', con=engine, if_exists='append', index=False)

    logger.info('Save to Postgres complete')
    return True

# Streamlit app
def run_app():
    """Start the Streamlit app UI. Imports Streamlit and Altair here to avoid side-effects on import."""
    import streamlit as st
    import altair as alt

    st.title("Pokémon Data Pipeline Dashboard")

    st.markdown("""
    This app demonstrates a data pipeline:
    1. **Extract**: Fetch data from PokeAPI (including abilities, evolutions).
    2. **Transform**: Process into a DataFrame with aggregates.
    3. **Load**: Save to Neon PostgreSQL for Grafana integration.
    4. **Visualize**: Interactive tables, charts, and stat comparisons.
    """)

    # Initialize database (showing errors in UI)
    try:
        init_db()
    except Exception as e:
        st.error(f"Database initialization failed: {e}")

    # Step 1: Extract and Load data
    if st.button("Run Pipeline (Fetch, Process, Save to PostgreSQL)"):
        with st.spinner("Fetching Pokémon data..."):
            pokemon_list = fetch_pokemon_list(limit=50)
            details = []
            for p in pokemon_list:
                detail = fetch_pokemon_details(p['url'])
                if detail:
                    details.append(detail)

            # Step 2: Transform into DataFrame
            df = pd.DataFrame(details)

            # Save to PostgreSQL
            try:
                save_to_postgres(df)
                st.success("Data saved to PostgreSQL successfully!")
            except Exception as e:
                st.error(f"Error saving to PostgreSQL: {e}")

            # Compute aggregates (explode list types)
            if 'types' in df.columns:
                df_exploded = df.explode('types')
                avg_stats_by_type = df_exploded.groupby('types').mean(numeric_only=True).reset_index()
            else:
                avg_stats_by_type = pd.DataFrame()

            # Cache data for interactivity
            st.session_state['df'] = df
            st.session_state['avg_stats'] = avg_stats_by_type

    # Display results if data is available
    if 'df' in st.session_state:
        df = st.session_state['df']
        avg_stats = st.session_state['avg_stats']

        st.subheader("Raw Data Table (First 10 Rows)")
        st.dataframe(df.head(10))

        st.subheader("Top 5 Fastest Pokémon")
        top_speed = df.sort_values('speed', ascending=False).head(5)[['name', 'speed', 'types_str']]
        st.table(top_speed)

        st.subheader("Average Stats by Type")
        st.dataframe(avg_stats)

        # Visualization: Bar chart for average speed by type
        if not avg_stats.empty:
            chart = alt.Chart(avg_stats).mark_bar().encode(
                x='types',
                y='speed',
                tooltip=['types', 'speed', 'attack', 'defense']
            ).properties(title="Average Speed by Pokémon Type")
            st.altair_chart(chart, use_container_width=True)

        # Interactive filter
        if 'types_str' in df.columns:
            types_options = sorted(df['types_str'].dropna().unique())
            if types_options:
                selected_type = st.selectbox("Filter by Type", options=types_options)
                filtered_df = df[df['types_str'].str.contains(selected_type, na=False)]
                st.subheader(f"Pokémon with Type: {selected_type}")
                st.dataframe(filtered_df)

        # Interactive Stat Comparisons
        st.subheader("Interactive Pokémon Stat Comparison")
        selected_pokemon = st.multiselect(
            "Select Pokémon to Compare (Choose 2 or more)",
            options=df['name'].tolist(),
            default=df['name'].tolist()[:2]
        )

        if len(selected_pokemon) >= 2:
            compare_df = df[df['name'].isin(selected_pokemon)][['name', 'hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']]
            melted_df = compare_df.melt(id_vars=['name'], var_name='Stat', value_name='Value')
            comparison_chart = alt.Chart(melted_df).mark_bar().encode(
                x=alt.X('Stat:N', title='Stat'),
                y=alt.Y('Value:Q', title='Base Value'),
                color=alt.Color('name:N', title='Pokémon'),
                tooltip=['name', 'Stat', 'Value']
            ).properties(
                title="Stat Comparison",
                width=600,
                height=400
            ).interactive()
            st.altair_chart(comparison_chart, use_container_width=True)
        else:
            st.info("Select at least 2 Pokémon to compare stats.")
    else:
        st.info("Click the button above to run the pipeline.")


if __name__ == '__main__':
    run_app()
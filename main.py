import streamlit as st
import requests
import pandas as pd
import altair as alt
from sqlalchemy import create_engine
import psycopg2
import threading
from prometheus_client import Counter, Gauge, start_http_server
import json
# PostgreSQL configuration (update with your credentials)
db_config = {
    "user": "neondb_owner",  # From Neon dashboard
    "password": "npg_kYHXo1n4WMPV",  # From Neon dashboard
    "host": "ep-raspy-tooth-adc28g5b-pooler.c-2.us-east-1.aws.neon.tech",  # From Neon dashboard
    "port": "5432",
    "database": "pokemon_db"  # Or "neondb" if you didn’t create a new database
}
# Create PostgreSQL database and table
def init_db():
    try:
        conn = psycopg2.connect(**db_config)
        conn.set_session(autocommit=True)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pokemon (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                types VARCHAR(255),
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
    except psycopg2.Error as err:
        st.error(f"Database error: {err}")

# Function to fetch list of Pokémon
def fetch_pokemon_list(limit=50):
    url = f"https://pokeapi.co/api/v2/pokemon?limit={limit}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['results']
    else:
        st.error("Failed to fetch Pokémon list.")
        return []

# Function to fetch details for a single Pokémon
def fetch_pokemon_details(url):
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        types = [t['type']['name'] for t in data['types']]
        stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
        abilities = [a['ability']['name'] for a in data['abilities']]
        # Fetch evolution chain ID (simplified)
        species_url = data['species']['url']
        species_response = requests.get(species_url)
        evolution_chain_id = None
        if species_response.status_code == 200:
            species_data = species_response.json()
            evolution_url = species_data['evolution_chain']['url']
            evolution_chain_id = int(evolution_url.split('/')[-2])
        stat_total = sum([
            stats.get('hp', 0), stats.get('attack', 0), stats.get('defense', 0),
            stats.get('special-attack', 0), stats.get('special-defense', 0), stats.get('speed', 0)
        ])
        return {
            'name': data['name'],
            'types': ', '.join(types),
            'height': data['height'],
            'weight': data['weight'],
            'hp': stats.get('hp', 0),
            'attack': stats.get('attack', 0),
            'defense': stats.get('defense', 0),
            'special_attack': stats.get('special-attack', 0),
            'special_defense': stats.get('special-defense', 0),
            'speed': stats.get('speed', 0),
            'stat_total': stat_total,
            'abilities': json.dumps(abilities),
            'evolution_chain_id': evolution_chain_id
        }
    return None

# Function to save DataFrame to PostgreSQL
def save_to_postgres(df):
    try:
        engine = create_engine(f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?sslmode=require")
        df.to_sql('pokemon', con=engine, if_exists='append', index=False)
        st.success("Data saved to PostgreSQL successfully!")
    except Exception as e:
        st.error(f"Error saving to PostgreSQL: {e}")

# Streamlit app
st.title("Pokémon Data Pipeline Dashboard")

st.markdown("""
This app demonstrates a data pipeline:
1. **Extract**: Fetch data from PokeAPI (including abilities, evolutions).
2. **Transform**: Process into a DataFrame with aggregates.
3. **Load**: Save to Neon PostgreSQL for Grafana integration.
4. **Visualize**: Interactive tables, charts, and stat comparisons.
""")

# Initialize database
init_db()

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
        save_to_postgres(df)
        
        # Compute aggregates
        avg_stats_by_type = df.explode('types').groupby('types').mean(numeric_only=True).reset_index()
        
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
    top_speed = df.sort_values('speed', ascending=False).head(5)[['name', 'speed', 'types']]
    st.table(top_speed)
    
    st.subheader("Average Stats by Type")
    st.dataframe(avg_stats)
    
    # Visualization: Bar chart for average speed by type
    chart = alt.Chart(avg_stats).mark_bar().encode(
        x='types',
        y='speed',
        tooltip=['types', 'speed', 'attack', 'defense']
    ).properties(title="Average Speed by Pokémon Type")
    st.altair_chart(chart, use_container_width=True)
    
    # Interactive filter
    selected_type = st.selectbox("Filter by Type", options=sorted(df['types'].unique()))
    filtered_df = df[df['types'].str.contains(selected_type)]
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
import streamlit as st
import requests
import pandas as pd
import altair as alt
from sqlalchemy import create_engine
import psycopg2
import threading
from prometheus_client import Counter, Gauge, start_http_server

# PostgreSQL configuration (update with your credentials)
db_config = {
    "user": "neondb_owner",  # From Neon dashboard
    "password": "npg_kYHXo1n4WMPV",  # From Neon dashboard
    "host": "ep-raspy-tooth-adc28g5b-pooler.c-2.us-east-1.aws.neon.tech",  # From Neon dashboard
    "port": "5432",
    "database": "pokemon_db"  # Or "neondb" if you didn’t create a new database
}
# Create PostgreSQL database and table if not exists
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
                speed INTEGER
            )
        """)
        cursor.close()
        conn.close()
    except psycopg2.Error as err:
        st.error(f"Database error: {err}")

# Prometheus metrics
PIPELINE_RUNS = Counter('pokemon_pipeline_runs_total', 'Total pipeline runs')
POKEMON_FETCHED = Gauge('pokemon_fetched', 'Number of pokemon fetched in last run')
LAST_RUN_SUCCESS = Gauge('pokemon_pipeline_last_success', '1 if last pipeline run succeeded, 0 otherwise')


def start_metrics_server(port: int = 8000):
    start_http_server(port)


# Start metrics server in background
metrics_thread = threading.Thread(target=start_metrics_server, args=(8000,), daemon=True)
metrics_thread.start()

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
        return {
            'name': data['name'],
            # keep types as list for explode and analyses
            'types': types,
            'height': data['height'],
            'weight': data['weight'],
            'hp': stats.get('hp', 0),
            'attack': stats.get('attack', 0),
            'defense': stats.get('defense', 0),
            'special_attack': stats.get('special-attack', 0),
            'special_defense': stats.get('special-defense', 0),
            'speed': stats.get('speed', 0)
        }
    return None

# Function to save DataFrame to PostgreSQL
def save_to_postgres(df):
    try:
        # Build SQLAlchemy engine URL; Neon may require sslmode=require
        engine = create_engine(f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?sslmode=require")
        # Convert list-like 'types' to comma-separated string for storage
        store_df = df.copy()
        if 'types' in store_df.columns:
            store_df['types'] = store_df['types'].apply(lambda x: ', '.join(x) if isinstance(x, (list, tuple)) else str(x))
        store_df.to_sql('pokemon', con=engine, if_exists='replace', index=False)
        st.success("Data saved to PostgreSQL successfully!")
    except Exception as e:
        st.error(f"Error saving to PostgreSQL: {e}")

# Streamlit app
st.title("Pokémon Data Pipeline Dashboard")

st.markdown("""
This app demonstrates a data pipeline:
1. **Extract**: Fetch data from PokeAPI.
2. **Transform**: Process into a DataFrame and compute aggregates.
3. **Load**: Save to PostgreSQL for Grafana integration.
4. **Visualize**: Interactive tables, charts, and stat comparisons.
""")

# Initialize database
init_db()

# Step 1: Extract and Load data
if st.button("Run Pipeline (Fetch, Process, Save to PostgreSQL)"):
    with st.spinner("Fetching Pokémon data..."):
        success = False
        try:
            PIPELINE_RUNS.inc()
            pokemon_list = fetch_pokemon_list(limit=50)  # Adjust limit as needed
            details = []
            for p in pokemon_list:
                detail = fetch_pokemon_details(p['url'])
                if detail:
                    details.append(detail)

            # Step 2: Transform into DataFrame
            df = pd.DataFrame(details)

            # Normalize types column to list-like and create types_str for display
            if 'types' in df.columns:
                df['types'] = df['types'].apply(lambda x: x if isinstance(x, (list, tuple)) else [x])
                df['types_str'] = df['types'].apply(lambda lst: ', '.join(lst))

            # Save to PostgreSQL
            save_to_postgres(df)

            # Compute aggregates (explode on list-like types)
            avg_stats_by_type = df.explode('types').groupby('types').mean(numeric_only=True).reset_index()

            # Cache data in session state for interactivity
            st.session_state['df'] = df
            st.session_state['avg_stats'] = avg_stats_by_type

            # update Prometheus metrics
            POKEMON_FETCHED.set(len(df))
            LAST_RUN_SUCCESS.set(1)
            success = True
        except Exception as e:
            LAST_RUN_SUCCESS.set(0)
            st.error(f"Pipeline error: {e}")
        finally:
            if not success:
                POKEMON_FETCHED.set(0)

# Display results if data is available
if 'df' in st.session_state:
    df = st.session_state['df']
    avg_stats = st.session_state.get('avg_stats', pd.DataFrame())
    
    st.subheader("Raw Data Table (First 10 Rows)")
    if 'types_str' in df.columns:
        display_df = df.copy()
        display_df['types'] = display_df['types_str']
    else:
        display_df = df
    st.dataframe(display_df.head(10))
    
    st.subheader("Top 5 Fastest Pokémon")
    top_speed = df.sort_values('speed', ascending=False).head(5)[['name', 'speed', 'types_str']]
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
    # build options from exploded types
    types_unique = sorted(avg_stats['types'].unique()) if not avg_stats.empty and 'types' in avg_stats.columns else []
    selected_type = st.selectbox("Filter by Type", options=types_unique)
    filtered_df = df[df['types'].apply(lambda lst: selected_type in lst if isinstance(lst, (list, tuple)) else False)]
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
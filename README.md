# Pokémon Data Pipeline

This Streamlit app fetches Pokémon data from the public PokeAPI, transforms it into a DataFrame, saves it to PostgreSQL (Neon-ready), and exposes Prometheus metrics for Grafana visualization.

Features
- Extract Pokémon data from PokeAPI
- Transform data into pandas DataFrame and compute aggregates
- Load data into MySQL
- Expose Prometheus metrics at `/metrics` (default port 8000)
- Streamlit UI for interactive exploration and charts

Quick start


1. Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Provide database credentials via environment variables (recommended)

Set the following environment variables before running the app. Do NOT commit secrets to the repo.

- POKEMON_DB_USER (default: neondb_owner)
- POKEMON_DB_PASSWORD (required for writing to DB)
- POKEMON_DB_HOST (default: localhost)
- POKEMON_DB_PORT (default: 5432)
- POKEMON_DB_NAME (default: pokemon_db)

If you are using Neon, ensure your connection/host and password values match the Neon dashboard and that the SQLAlchemy URL uses `sslmode=require` (the app appends this by default).

3. Run the Streamlit app locally:

```bash
# example (bash/zsh)
export POKEMON_DB_PASSWORD="your-db-password"
export POKEMON_DB_HOST="your-db-host"
streamlit run main.py
```

4. Run with Docker (recommended: pass secrets as env vars at runtime):

```bash
# build
docker build -t pokemon-app:latest .

# run (pass secrets via -e or use a secret manager)
docker run --rm -e POKEMON_DB_PASSWORD="$POKEMON_DB_PASSWORD" -e POKEMON_DB_HOST="$POKEMON_DB_HOST" -p 8501:8501 pokemon-app:latest
```

5. Run tests

```bash
pytest -q
```

4. Metrics: Prometheus metrics server starts on port 8000 by default. Configure Prometheus to scrape `http://<host>:8000/metrics`.

Grafana

- Import a dashboard or create panels that query Prometheus metrics `pokemon_pipeline_runs_total`, `pokemon_fetched`, and `pokemon_pipeline_last_success`.
 - Import a dashboard or create panels that query Prometheus metrics `pokemon_pipeline_runs_total`, `pokemon_fetched`, and `pokemon_pipeline_last_success`.

Notes

- Pushing to GitHub requires git credentials configured on your machine. See the steps below to push.

Push to GitHub

```bash
git init
git add .
git commit -m "Add Streamlit Pokemon pipeline with Prometheus metrics"
git remote add origin https://github.com/LakshmiSravya123/pokemon.git
git push -u origin main
```

If you don't have permission to push, you'll need to authenticate or create a fork and push there.

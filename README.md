# Pokémon Data Pipeline

This Streamlit app fetches Pokémon data from the public PokeAPI, transforms it into a DataFrame, saves it to MySQL, and exposes Prometheus metrics for Grafana visualization.

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

2. Update MySQL credentials in `main.py` db_config.

3. Run the Streamlit app:

```bash
streamlit run main.py
```

4. Metrics: Prometheus metrics server starts on port 8000 by default. Configure Prometheus to scrape `http://<host>:8000/metrics`.

Grafana

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

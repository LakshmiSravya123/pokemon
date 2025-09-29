"""Lightweight smoke test: import main module and run fetch_pokemon_list with limit=1.
This avoids starting Streamlit UI and only checks that core functions import and the HTTP call works.
"""
import main

if __name__ == '__main__':
    results = main.fetch_pokemon_list(limit=1)
    if isinstance(results, list):
        print('fetch_pokemon_list OK:', results)
    else:
        raise SystemExit('fetch_pokemon_list returned unexpected type')

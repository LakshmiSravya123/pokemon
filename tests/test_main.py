import json
import pytest

import main


class DummyResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def test_fetch_pokemon_list_success(monkeypatch):
    data = {'results': [{'name': 'bulbasaur', 'url': 'https://pokeapi.co/api/v2/pokemon/1/'}]}

    def fake_get(url, timeout=None):
        return DummyResponse(status_code=200, json_data=data)

    monkeypatch.setattr(main.requests, 'get', fake_get)
    res = main.fetch_pokemon_list(limit=1)
    assert isinstance(res, list)
    assert res[0]['name'] == 'bulbasaur'


def test_fetch_pokemon_details_success(monkeypatch):
    # Minimal pokemon detail structure
    detail = {
        'name': 'bulbasaur',
        'types': [{'type': {'name': 'grass'}}],
        'stats': [{'stat': {'name': 'hp'}, 'base_stat': 45}],
        'abilities': [{'ability': {'name': 'overgrow'}}],
        'species': {'url': 'https://pokeapi.co/api/v2/pokemon-species/1/'}
    }

    species_detail = {'evolution_chain': {'url': 'https://pokeapi.co/api/v2/evolution-chain/1/'}}

    def fake_get(url, timeout=None):
        if 'pokemon-species' in url:
            return DummyResponse(status_code=200, json_data=species_detail)
        return DummyResponse(status_code=200, json_data=detail)

    monkeypatch.setattr(main.requests, 'get', fake_get)
    res = main.fetch_pokemon_details('https://pokeapi.co/api/v2/pokemon/1/')
    assert res is not None
    assert res['name'] == 'bulbasaur'
    assert isinstance(res['types'], list)
    assert res['types'][0] == 'grass'

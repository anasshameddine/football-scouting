"""Tests de l'API. Ils tournent sur les vraies données locales ; ignorés si elles manquent."""

import pytest
from fastapi.testclient import TestClient

from api.main import ROOT, app

pytestmark = pytest.mark.skipif(
    not (ROOT / "ml" / "models" / "valeur_xgb.json").exists()
    or not (ROOT / "data" / "processed" / "ml_base.csv.gz").exists()
    or not (ROOT / "data" / "processed" / "joueurs_propres.csv").exists(),
    reason="modèle ou données absents : lancer run_pipeline.ps1")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["metriques_test"]["r2"] > 0.8


def test_predict_joueur_connu(client):
    r = client.post("/predict-value", json={"player": "Ounahi"})
    assert r.status_code == 200
    j = r.json()
    assert j["valeur_predite_basse_eur"] < j["valeur_predite_eur"] < j["valeur_predite_haute_eur"]


def test_predict_joueur_inconnu(client):
    assert client.post("/predict-value", json={"player": "Zzzzqx"}).status_code == 404


def test_predict_manuel_coherent(client):
    base = {"age": 23, "minutes": 2000, "matches": 28, "starts": 25,
            "position": "Centre-Forward", "league": "ENG-Premier League"}
    fort = client.post("/predict-value", json={**base, "team_avg_value_eur": 40e6}).json()
    faible = client.post("/predict-value", json={**base, "team_avg_value_eur": 2e6}).json()
    assert fort["valeur_predite_eur"] > faible["valeur_predite_eur"]


def test_predict_manuel_incomplet(client):
    assert client.post("/predict-value", json={"age": 20}).status_code == 422
    r = client.post("/predict-value", json={"age": 20, "minutes": 900, "position": "Gardien",
                                            "league": "ESP-La Liga"})
    assert r.status_code == 422


def test_similar_players(client):
    r = client.get("/similar-players", params={"player": "Ounahi", "n": 5})
    assert r.status_code == 200
    top = r.json()["top"]
    assert len(top) == 5
    sims = [p["similarite"] for p in top]
    assert sims == sorted(sims, reverse=True)
    assert set(r.json()["par_budget"]) == {"low", "medium", "high", "superstar"}


def test_similar_players_pca(client):
    r = client.get("/similar-players", params={"player": "Ounahi", "n": 5, "method": "pca"})
    assert r.status_code == 200 and r.json()["method"] == "pca"
    sims = [p["similarite"] for p in r.json()["top"]]
    assert len(sims) == 5 and sims == sorted(sims, reverse=True)
    assert client.get("/similar-players", params={"player": "Ounahi", "method": "x"}).status_code == 422


def test_similar_players_filtre_marocains(client):
    r = client.get("/similar-players", params={"player": "Ounahi", "moroccan_only": True})
    assert r.status_code == 200
    assert all(p["is_moroccan"] for p in r.json()["top"])


def test_similar_players_inconnu(client):
    assert client.get("/similar-players", params={"player": "Zzzzqx"}).status_code == 404


def test_undervalued(client):
    r = client.get("/undervalued", params={"n": 5})
    assert r.status_code == 200
    for p in r.json():
        assert p["valeur_reelle_eur"] < p["valeur_predite_basse_eur"] and p["age"] <= 28

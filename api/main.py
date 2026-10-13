"""
API de scouting : valeur marchande prédite et joueurs similaires.

Elle réutilise tel quel le code existant :
  - ml/features.py   -> mêmes variables que l'entraînement
  - ml/models/       -> modèle XGBoost sauvegardé par train_value.py
  - ml/profiles.py   -> similarité par percentiles (celle du dashboard)

Lancer :  uvicorn api.main:app --reload      puis  http://localhost:8000/docs
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("SCOUT_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
from features import POSTES, LIGUES, construire, filtrer  # noqa: E402
from profiles import charger_base, norm, similaires  # noqa: E402

ETAT: dict = {}


def charger():
    """Charge le modèle, prédit une fois pour toutes les lignes connues, charge la base de profils."""
    meta = json.loads((ROOT / "ml" / "models" / "valeur_meta.json").read_text(encoding="utf-8"))
    modele = xgb.XGBRegressor()
    modele.load_model(str(ROOT / "ml" / "models" / "valeur_xgb.json"))
    ml = pd.read_csv(ROOT / "data" / "processed" / "ml_base.csv.gz", low_memory=False,
                     dtype={"season": str})
    X, y, m = construire(filtrer(ml))
    X = X[meta["variables"]]
    pred = modele.predict(X)
    lignes = m.assign(
        valeur_reelle_eur=np.exp(y).round(-3),
        valeur_predite_eur=np.exp(pred).round(-3),
        valeur_predite_basse_eur=np.exp(pred - meta["decalage_basse"]).round(-3),
        valeur_predite_haute_eur=np.exp(pred - meta["decalage_haute"]).round(-3))
    lignes["nom_norm"] = lignes["player"].map(norm)
    ETAT.update(meta=meta, modele=modele, lignes=lignes,
                profils=charger_base(ROOT / "data" / "processed" / "joueurs_propres.csv"))


@asynccontextmanager
async def lifespan(app):
    charger()
    yield
    ETAT.clear()


app = FastAPI(
    title="Scouting API",
    description="Valeur marchande prédite (XGBoost) et recherche de joueurs similaires "
                "(percentiles par poste) sur 14 championnats.",
    version="1.0.0", lifespan=lifespan)


def propre(df):
    """DataFrame -> liste de dicts JSON-compatibles (NaN -> null)."""
    return json.loads(df.replace({np.nan: None}).to_json(orient="records"))


# ----------------------------------------------------------------------------- schémas
class PredictRequest(BaseModel):
    """Soit `player` (+ `season`), soit des caractéristiques saisies à la main."""
    player: Optional[str] = Field(None, examples=["Azzedine Ounahi"])
    season: Optional[str] = Field(None, description="Ex. 2526. Par défaut : la plus récente.")
    age: Optional[float] = Field(None, ge=15, le=45)
    minutes: Optional[float] = Field(None, ge=0)
    matches: Optional[float] = Field(None, ge=0, description="Matchs joués")
    starts: Optional[float] = Field(None, ge=0, description="Titularisations")
    position: Optional[str] = Field(None, description=f"Un de : {', '.join(POSTES)}")
    league: Optional[str] = Field(None, description=f"Un de : {', '.join(LIGUES)}")
    team_avg_value_eur: Optional[float] = Field(
        None, gt=0, description="Valeur moyenne des coéquipiers : mesure le niveau du club")
    goals_p90: Optional[float] = None
    assists_p90: Optional[float] = None


# ----------------------------------------------------------------------------- routes
@app.get("/health")
def health():
    return {"status": "ok", "lignes": len(ETAT["lignes"]), "modele": ETAT["meta"]["date"],
            "metriques_test": ETAT["meta"]["metriques_test_2025_26"]}


@app.post("/predict-value")
def predict_value(req: PredictRequest):
    """Valeur marchande prédite avec une fourchette à 80 %."""
    meta, modele = ETAT["meta"], ETAT["modele"]
    if req.player:
        L = ETAT["lignes"]
        m = L[L["nom_norm"].str.contains(norm(req.player), regex=False)]
        if req.season:
            m = m[m["season"] == req.season]
        if m.empty:
            raise HTTPException(404, f"Joueur introuvable : {req.player}")
        m = m.sort_values(["season", "playing_time_min"], ascending=False)
        cols = ["player", "team", "league", "season", "age", "valeur_reelle_eur",
                "valeur_predite_eur", "valeur_predite_basse_eur", "valeur_predite_haute_eur"]
        r = propre(m.head(1)[cols])[0]
        r["ecart_pct"] = round((r["valeur_predite_eur"] / r["valeur_reelle_eur"] - 1) * 100)
        return {"source": "joueur connu", **r}

    if req.age is None or req.minutes is None or not req.position or not req.league:
        raise HTTPException(422, "Donner `player`, ou au minimum age, minutes, position et league.")
    if req.position not in POSTES:
        raise HTTPException(422, f"position inconnue, choisir parmi {POSTES}")
    if req.league not in LIGUES:
        raise HTTPException(422, f"league inconnue, choisir parmi {LIGUES}")
    x = pd.DataFrame(np.nan, index=[0], columns=meta["variables"])
    x["age"], x["minutes"] = req.age, req.minutes
    if req.matches:
        x["minutes_par_match"] = req.minutes / req.matches
        if req.starts is not None:
            x["part_titulaire"] = req.starts / req.matches
    for p in POSTES:
        x[f"poste_{p}"] = int(p == req.position)
    for lg in LIGUES:
        x[f"ligue_{lg}"] = int(lg == req.league)
    x["big5"] = int(req.league in LIGUES[:5])
    if req.goals_p90 is not None:
        x["performance_gls_p90"] = req.goals_p90
    if req.assists_p90 is not None:
        x["performance_ast_p90"] = req.assists_p90
    if req.team_avg_value_eur:
        x["equipe_log_valeur_autres"] = np.log(req.team_avg_value_eur)
    p = float(modele.predict(x[meta["variables"]])[0])
    return {"source": "caractéristiques saisies",
            "valeur_predite_eur": round(float(np.exp(p)), -3),
            "valeur_predite_basse_eur": round(float(np.exp(p - meta["decalage_basse"])), -3),
            "valeur_predite_haute_eur": round(float(np.exp(p - meta["decalage_haute"])), -3),
            "avertissement": "Variables manquantes laissées vides : estimation moins précise."}


@app.get("/similar-players")
def similar_players(
        player: str = Query(..., examples=["Jeremy Doku"]),
        mode: str = Query("all", pattern="^(all|big5)$",
                          description="all : 14 championnats ; big5 : 5 grands, avec xG/xA"),
        n: int = Query(10, ge=1, le=50),
        age_max: Optional[int] = Query(None, ge=15, le=45),
        moroccan_only: bool = False,
        per_budget: int = Query(3, ge=1, le=10),
        method: str = Query("percentiles", pattern="^(percentiles|pca)$",
                            description="percentiles : distance entre percentiles ; "
                                        "pca : ACP puis plus proches voisins")):
    """Joueurs au profil le plus proche, au global et par tranche de budget."""
    try:
        top, tranches, _ = similaires(ETAT["profils"], player, mode=mode, n=n, age_max=age_max,
                                      marocains=moroccan_only, par_budget=per_budget,
                                      methode=method)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"player": player, "mode": mode, "method": method, "top": propre(top),
            "par_budget": {t: propre(d) for t, d in tranches.items()}}


@app.get("/undervalued")
def undervalued(n: int = Query(20, ge=1, le=100), moroccan_only: bool = False,
                age_max: int = Query(28, ge=15, le=45),
                max_value_eur: Optional[float] = Query(None, gt=0)):
    """Joueurs de la dernière saison dont la valeur est sous la fourchette basse prédite."""
    L = ETAT["lignes"]
    d = L[(L["season"] == L["season"].max()) & (L["playing_time_min"] >= 900)
          & (L["valeur_reelle_eur"] >= 500_000) & (L["age"] <= age_max)
          & (L["valeur_reelle_eur"] < L["valeur_predite_basse_eur"])].copy()
    d["ecart_pct"] = ((d["valeur_predite_eur"] / d["valeur_reelle_eur"] - 1) * 100).round(0)
    d = d[d["ecart_pct"] >= 50]
    if moroccan_only:
        d = d[d["is_moroccan"].fillna(False).astype(bool)]
    if max_value_eur:
        d = d[d["valeur_reelle_eur"] <= max_value_eur]
    d = d.sort_values("ecart_pct", ascending=False).head(n)
    return propre(d[["player", "team", "league", "season", "age", "valeur_reelle_eur",
                     "valeur_predite_eur", "valeur_predite_basse_eur", "ecart_pct"]])

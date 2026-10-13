"""
Modèle de valeur marchande : entraînement, comparaison des essais, analyse des erreurs,
prédictions et liste des joueurs sous-cotés.

    python ml/train_value.py              # lit data/processed/ml_base.csv.gz
    python ml/train_value.py --pg         # écrit aussi ml.valeur_predite dans PostgreSQL

Découpage dans le temps (jamais de mélange passé/futur pour les métriques) :
    entraînement 2021-22 à 2023-24  |  validation 2024-25  |  test 2025-26
Essais comparés : régression linéaire (Ridge), XGBoost sans puis avec le niveau du club.
Tous les essais sont suivis dans MLflow (mlflow.db à la racine, interface : `mlflow ui --backend-store-uri sqlite:///mlflow.db`).

Prédictions par joueur : validation croisée « une saison à la fois » (chaque saison est prédite
par un modèle qui ne l'a jamais vue), donc aucune valeur prédite n'est calculée sur ses propres données.
"""

import argparse
import json
import sys
import warnings
from contextlib import nullcontext
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import construire, filtrer  # noqa: E402

try:
    import mlflow
except ImportError:                      # le script marche sans MLflow, sans suivi
    mlflow = None

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
MODELES = Path(__file__).resolve().parent / "models"
DOCS = ROOT / "docs"

TRAIN, VALID, TEST = ["2122", "2223", "2324"], ["2425"], ["2526"]
SAISONS = TRAIN + VALID + TEST
XGB = dict(learning_rate=0.03, max_depth=5, subsample=0.8, colsample_bytree=0.8,
           min_child_weight=5, reg_lambda=1.0, n_jobs=4, random_state=42)
PALIERS = [(0, 5e6, "moins de 5 M€"), (5e6, 25e6, "5 à 25 M€"),
           (25e6, 70e6, "25 à 70 M€"), (70e6, 1e12, "plus de 70 M€")]


def metriques(pred, y):
    e = pred - y
    ape = np.abs(np.exp(pred) / np.exp(y) - 1)
    return {"rmse_log": float(np.sqrt((e ** 2).mean())), "mae_log": float(e.abs().mean()),
            "erreur_mediane_pct": float(np.median(ape) * 100),
            "part_a_moins_de_50pct": float((ape <= 0.5).mean() * 100),
            "r2": float(1 - (e ** 2).sum() / ((y - y.mean()) ** 2).sum())}


def xgb_fit(X, y, X_val=None, y_val=None, n_estimators=None):
    if n_estimators is None:
        m = xgb.XGBRegressor(n_estimators=4000, early_stopping_rounds=150, **XGB)
        m.fit(X, y, eval_set=[(X_val, y_val)], verbose=False)
    else:
        m = xgb.XGBRegressor(n_estimators=n_estimators, **XGB)
        m.fit(X, y, verbose=False)
    return m


def ridge():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         RidgeCV(alphas=np.logspace(-2, 3, 20)))


def essai(nom, params, fn, mlf):
    """Exécute fn() -> (métriques validation, métriques test, artefacts) et suit dans MLflow."""
    ctx = mlflow.start_run(run_name=nom) if mlf else nullcontext()
    with ctx:
        val, test, arts = fn()
        if mlf:
            mlflow.log_params(params)
            mlflow.log_metrics({f"val_{k}": v for k, v in val.items()})
            mlflow.log_metrics({f"test_{k}": v for k, v in test.items()})
            for a in arts:
                mlflow.log_artifact(str(a))
    print(f"{nom:34s} val R²={val['r2']:.3f} erreur méd.={val['erreur_mediane_pct']:.0f} % | "
          f"test R²={test['r2']:.3f} erreur méd.={test['erreur_mediane_pct']:.0f} % "
          f"(±50 % : {test['part_a_moins_de_50pct']:.0f} %)")
    return {"essai": nom, **{f"val_{k}": v for k, v in val.items()},
            **{f"test_{k}": v for k, v in test.items()}}


def main(pg=False):
    df = pd.read_csv(DATA / "ml_base.csv.gz", low_memory=False, dtype={"season": str})
    d = filtrer(df)
    mlf = mlflow is not None
    if mlf:
        mlflow.set_tracking_uri(f"sqlite:///{(ROOT / 'mlflow.db').as_posix()}")
        mlflow.set_experiment("valeur_marchande")
    DATA.mkdir(parents=True, exist_ok=True)
    MODELES.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    X_ctx, y, meta = construire(d, avec_contexte=True)
    ok = y.notna()
    X_ctx, y, meta = X_ctx[ok], y[ok], meta[ok]
    X_sans = X_ctx.drop(columns=["equipe_log_valeur_autres"])
    tr = meta["season"].isin(TRAIN)
    va = meta["season"].isin(VALID)
    te = meta["season"].isin(TEST)
    trva = tr | va
    print(f"Lignes : entraînement {tr.sum()}, validation {va.sum()}, test {te.sum()}\n")

    lignes, best = [], {}

    def f_ridge():
        m = ridge().fit(X_ctx[tr], y[tr])
        v = metriques(pd.Series(m.predict(X_ctx[va]), index=y[va].index), y[va])
        m2 = ridge().fit(X_ctx[trva], y[trva])
        t = metriques(pd.Series(m2.predict(X_ctx[te]), index=y[te].index), y[te])
        return v, t, []
    lignes.append(essai("1. Ridge (linéaire, avec club)", {"modele": "ridge", "contexte_club": True},
                        f_ridge, mlf))

    def f_xgb(X, cle):
        def inner():
            m = xgb_fit(X[tr], y[tr], X[va], y[va])
            v = metriques(pd.Series(m.predict(X[va]), index=y[va].index), y[va])
            n = int(m.best_iteration * 1.1) + 1
            best[cle] = n
            m2 = xgb_fit(X[trva], y[trva], n_estimators=n)
            t = metriques(pd.Series(m2.predict(X[te]), index=y[te].index), y[te])
            best[cle + "_modele"] = m2
            return v, t, []
        return inner
    lignes.append(essai("2. XGBoost (sans niveau du club)",
                        {"modele": "xgboost", "contexte_club": False, **XGB},
                        f_xgb(X_sans, "sans"), mlf))
    lignes.append(essai("3. XGBoost (avec niveau du club)",
                        {"modele": "xgboost", "contexte_club": True, **XGB},
                        f_xgb(X_ctx, "avec"), mlf))
    n_final = best["avec"]
    modele = best["avec_modele"]

    # --- analyse des erreurs sur le test (2025-26) -----------------------------------------
    pred_test = pd.Series(modele.predict(X_ctx[te]), index=y[te].index)
    err = meta[te].assign(y=y[te], pred=pred_test)
    err["ape"] = np.abs(np.exp(err["pred"]) / np.exp(err["y"]) - 1) * 100
    err["biais_log"] = err["pred"] - err["y"]

    def resume(g):
        return pd.Series({"joueurs": len(g), "erreur_mediane_pct": g["ape"].median(),
                          "biais_mediane_pct": (np.exp(g["biais_log"].median()) - 1) * 100})
    par_poste = err.groupby("tm_sub_position").apply(resume).sort_values("joueurs", ascending=False)
    par_ligue = err.groupby("league").apply(resume).sort_values("joueurs", ascending=False)
    err["palier"] = pd.cut(np.exp(err["y"]), [p[0] for p in PALIERS] + [PALIERS[-1][1]],
                           labels=[p[2] for p in PALIERS], right=False)
    par_palier = err.groupby("palier", observed=True).apply(resume)
    imp = pd.Series(modele.get_booster().get_score(importance_type="gain")).sort_values(ascending=False)
    imp = (imp / imp.sum() * 100).round(1).rename("importance_pct")
    for nom, t in [("erreurs_par_poste", par_poste), ("erreurs_par_championnat", par_ligue),
                   ("erreurs_par_palier_valeur", par_palier), ("importance_variables", imp.to_frame())]:
        t.round(1).to_csv(DATA / f"valeur_{nom}.csv")
    if mlf:
        with mlflow.start_run(run_name="analyse des erreurs (test 2025-26)"):
            for nom in ["erreurs_par_poste", "erreurs_par_championnat",
                        "erreurs_par_palier_valeur", "importance_variables"]:
                mlflow.log_artifact(str(DATA / f"valeur_{nom}.csv"))

    # --- prédictions : une saison à la fois (aucune saison prédite par un modèle qui l'a vue) ---
    pred = pd.Series(np.nan, index=y.index)
    for s in SAISONS:
        masque = meta["season"] == s
        m = xgb_fit(X_ctx[~masque], y[~masque], n_estimators=n_final)
        pred[masque] = m.predict(X_ctx[masque])
    resid = (pred - y)
    q10, q90 = resid.quantile(0.10), resid.quantile(0.90)
    out = meta.assign(valeur_reelle_eur=np.exp(y).round(-3),
                      valeur_predite_eur=np.exp(pred).round(-3),
                      valeur_predite_basse_eur=np.exp(pred - q90).round(-3),
                      valeur_predite_haute_eur=np.exp(pred - q10).round(-3))
    out["ecart_pct"] = ((out["valeur_predite_eur"] / out["valeur_reelle_eur"] - 1) * 100).round(0)
    out = out.drop(columns=["valeur_fin_saison_eur"]).sort_values(["season", "ecart_pct"],
                                                                 ascending=[True, False])
    out.to_csv(DATA / "valeur_predite.csv", index=False)

    # --- joueurs sous-cotés de la dernière saison -----------------------------------------
    # Critères : valeur réelle en dessous de la FOURCHETTE basse prédite (même l'estimation
    # prudente est plus haute), au moins 50 % d'écart, 900 minutes, 28 ans max, 500 k€ min
    # (les petites valeurs Transfermarkt sont arrondies par paliers : trop de bruit en dessous).
    cur = out[(out["season"] == TEST[0]) & (out["playing_time_min"] >= 900)
              & (out["valeur_reelle_eur"] >= 500_000) & (out["age"] <= 28)
              & (out["ecart_pct"] >= 50)
              & (out["valeur_reelle_eur"] < out["valeur_predite_basse_eur"])].copy()
    cur["ecart_eur"] = cur["valeur_predite_eur"] - cur["valeur_reelle_eur"]
    cur = cur.sort_values("ecart_eur", ascending=False)
    cur.to_csv(DATA / "joueurs_sous_cotes.csv", index=False)
    print(f"\nJoueurs sous-cotés 2025-26 : {len(cur)}")
    cols = ["player", "team", "league", "age", "valeur_reelle_eur", "valeur_predite_eur", "ecart_pct"]
    print(cur[cols].head(10).to_string(index=False))
    mar = out[(out["season"] == TEST[0]) & out["is_moroccan"] & (out["playing_time_min"] >= 900)
              & (out["ecart_pct"] >= 30) & (out["age"] <= 30)]
    print("\nMarocains avec une valeur prédite au moins 30 % au-dessus de la valeur réelle :")
    print(mar.sort_values("ecart_pct", ascending=False)[cols].head(10).to_string(index=False))

    # --- modèle final (toutes saisons) et documentation ------------------------------------
    final = xgb_fit(X_ctx, y, n_estimators=n_final)
    final.save_model(str(MODELES / "valeur_xgb.json"))
    (MODELES / "valeur_meta.json").write_text(json.dumps({
        "date": str(date.today()), "variables": list(X_ctx.columns), "n_arbres": n_final,
        "cible": "log(valeur Transfermarkt au 30 juin)", "saisons": SAISONS,
        "decalage_basse": float(q90), "decalage_haute": float(q10),
        "metriques_test_2025_26": {k[5:]: v for k, v in lignes[2].items() if k.startswith("test_")},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if mlf:
        with mlflow.start_run(run_name="modele final (toutes saisons)"):
            mlflow.log_params({**XGB, "n_arbres": n_final})
            mlflow.log_artifact(str(MODELES / "valeur_xgb.json"))
            mlflow.log_artifact(str(MODELES / "valeur_meta.json"))

    comp = pd.DataFrame(lignes).set_index("essai")
    tableau = comp[["test_r2", "test_erreur_mediane_pct", "test_part_a_moins_de_50pct",
                    "test_rmse_log", "val_r2", "val_erreur_mediane_pct"]].round(2)
    tableau.columns = ["R² test", "Erreur médiane test (%)", "Part à ±50 % test (%)",
                       "RMSE log test", "R² validation", "Erreur médiane validation (%)"]
    md = ["# Modèle de valeur marchande : résultats", "",
          f"Généré le {date.today()}. Test = saison 2025-26, jamais vue pendant le réglage.", "",
          tableau.to_markdown(), "", "## Erreur par poste (test)", "", par_poste.round(1).to_markdown(),
          "", "## Erreur par palier de valeur (test)", "", par_palier.round(1).to_markdown(),
          "", "## Variables les plus utiles", "", imp.head(12).to_markdown(), ""]
    (DOCS / "modele_valeur_resultats.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nRésultats écrits dans {DOCS / 'modele_valeur_resultats.md'}")

    if pg:
        from sqlalchemy import create_engine, text
        sys.path.insert(0, str(ROOT / "ingestion"))
        from common import pg_url
        eng = create_engine(pg_url())
        with eng.begin() as cx:
            cx.execute(text("create schema if not exists ml"))
        out.to_sql("valeur_predite", eng, schema="ml", if_exists="replace", index=False)
        print("ml.valeur_predite écrite dans PostgreSQL")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pg", action="store_true")
    main(p.parse_args().pg)

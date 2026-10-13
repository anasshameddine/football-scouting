"""Tests de l'assistant sans Ollama ni PostgreSQL (le modèle et la base sont simulés)."""

import pandas as pd
import pytest

from assistant import evaluer, rag, report, sql_agent


# ------------------------------------------------------------------ texte vers SQL
def test_extraire_sql_bloc_et_texte_brut():
    assert sql_agent.extraire_sql("Voici :\n```sql\nselect 1;\n```\nVoilà") == "select 1"
    assert sql_agent.extraire_sql("La requête est : SELECT player FROM gold.dim_player;") == \
        "SELECT player FROM gold.dim_player"


@pytest.mark.parametrize("sql", [
    "select player from gold.dim_player",
    "with t as (select * from gold.fact_player_season) select count(*) from t",
    "select player from gold.dim_player where player = 'Do; drop'",
    "select a.player from gold.dim_player a union select b.player from ml.valeur_predite b",
])
def test_verifier_accepte_les_lectures(sql):
    assert sql_agent.verifier(sql) == sql


@pytest.mark.parametrize("sql", [
    "delete from gold.dim_player",
    "select 1; drop table gold.dim_player",
    "select * from pg_catalog.pg_user",
    "select * from information_schema.tables",
    "select * into gold.copie from gold.dim_player",
    "select pg_sleep(60)",
    "update gold.dim_player set player = 'x'",
])
def test_verifier_refuse_le_reste(sql):
    with pytest.raises(sql_agent.RequeteRefusee):
        sql_agent.verifier(sql)


def test_agent_corrige_apres_erreur(monkeypatch):
    """1re requête refusée, 2e en erreur PostgreSQL, 3e correcte : l'agent finit par répondre."""
    monkeypatch.setattr(sql_agent, "contexte", lambda db_url=None: ("schéma", {"derniere": "2526"}))

    def executer(sql, db_url=None):
        if "inconnue" in sql:
            raise RuntimeError('column "inconnue" does not exist')
        return pd.DataFrame({"n": [102]}), False
    monkeypatch.setattr(sql_agent, "executer", executer)
    reponses = iter(["delete from gold.dim_player",
                     "```sql\nselect inconnue from gold.dim_player\n```",
                     "```sql\nselect count(*) as n from gold.dim_player where is_moroccan\n```"])
    rep = sql_agent.generer_et_executer("Combien de Marocains ?", chat=lambda m, **k: next(reponses))
    assert rep.erreur is None and rep.donnees["n"].iloc[0] == 102
    assert len(rep.essais) == 2 and "does not exist" in rep.essais[1][1]


# ------------------------------------------------------------------ évaluation
def test_meme_resultat_tolere_millions_et_colonnes_en_plus():
    ref = pd.DataFrame({"player": ["A", "B"], "valeur": [80_000_000, 35_000_000]})
    pred = pd.DataFrame({"player": ["A", "B"], "club": ["X", "Y"], "valeur_meur": [80.0, 35.0]})
    assert evaluer.meme_resultat(ref, pred, ordonne=True)


def test_meme_resultat_refuse_un_mauvais_resultat():
    ref = pd.DataFrame({"player": ["A", "B"], "buts": [10, 8]})
    assert not evaluer.meme_resultat(ref, pd.DataFrame({"player": ["A"], "buts": [10]}))
    assert not evaluer.meme_resultat(ref, pd.DataFrame({"player": ["A", "C"], "buts": [10, 8]}))
    assert not evaluer.meme_resultat(ref, pd.DataFrame({"player": ["B", "A"], "buts": [8, 10]}), ordonne=True)


def test_questions_de_test_sont_valides():
    from assistant.questions_test import QUESTIONS, QUESTIONS_NOUVELLES
    toutes = QUESTIONS + QUESTIONS_NOUVELLES
    assert len(QUESTIONS) == 20 and len({q["id"] for q in toutes}) == 30
    for q in toutes:
        sql_agent.verifier(q["sql"].format(derniere="2526"))


# ------------------------------------------------------------------ RAG
ARTICLE = ("Bilal El Khannouss (born 2004) is a Moroccan footballer.\n\n"
           "== Club career ==\n=== Genk ===\n" + "He played for Genk and scored many goals. " * 50 +
           "\n== Career statistics ==\n=== Club ===\nGenk 2021 10 2 and lots of table numbers here " * 3 +
           "\n== Honours ==\nGenk: Belgian Cup runner-up 2023, Eredivisie winner 2024, and a long enough honours line for the test.\n"
           "== References ==\nSome reference that should never be indexed in the vector store.\n")


def test_decouper_retire_les_sections_inutiles():
    passages = rag.decouper(ARTICLE)
    sections = {s for s, _ in passages}
    assert {"Genk", "Honours"} <= sections
    assert not sections & {"Career statistics", "Club", "References"}
    assert all(len(p) <= rag.TAILLE for _, p in passages)


def test_joueurs_cites_nom_complet_puis_nom_de_famille():
    index = [(1, "Bilal El Khannouss"), (2, "Brahim Díaz"), (3, "Luis Díaz"), (4, "Achraf Hakimi")]
    assert rag.joueurs_cites("Où a joué Brahim Diaz ?", index) == [2]
    assert sorted(rag.joueurs_cites("Quels clubs pour Diaz ?", index)) == [2, 3]
    assert rag.joueurs_cites("Formation de El Khannouss", index) == [1]
    assert rag.joueurs_cites("Qui a gagné la Coupe d'Afrique ?", index) == []


# ------------------------------------------------------------------ rapport
FAITS = {"joueur": "Ismael Saibari", "age": 24, "club": "PSV", "valeur_actuelle_meur": 40.0,
         "estimation_modele_meur": 31.5, "fourchette_meur": "20.1 - 48.0",
         "points_forts": [("Passes clés", 2.31, 94)],
         "saisons": [{"saison": "2025-2026", "club": "PSV", "minutes": 2100, "matchs": 25, "buts": 11,
                      "passes": 7, "xg": None, "xa": None}]}


def test_controle_des_chiffres():
    texte = report.faits_texte(FAITS)
    assert "Passes clés : 2.31, percentile 94" in texte
    rapport = "Valeur 40 M€ contre 31,5 M€ estimés, 94e percentile, 11 buts en 2100 minutes, 3 matchs."
    assert report.chiffres_inventes(rapport, texte) == []
    assert report.chiffres_inventes("Il a marqué 17 buts pour 55 M€.", texte) == ["17", "55"]


def test_rediger_utilise_les_sections_et_signale_les_inventions():
    vu = {}

    def chat(messages, **k):
        vu["prompt"] = messages[-1]["content"]
        return "## Résumé\nJoueur à 40 M€ qui a marqué 19 buts."
    r = report.rediger(FAITS, "fr", chat=chat)
    assert "## Verdict du scout" in vu["prompt"] and "Ismael Saibari" in vu["prompt"]
    assert r.chiffres_non_verifies == ["19"]


def test_corriger_round_convertit_en_numeric():
    sql = "select round(avg(p.tm_height_cm), 1) from gold.dim_player p"
    assert "CAST(AVG(p.tm_height_cm) AS DECIMAL)" in sql_agent.corriger_round(sql)
    assert sql_agent.corriger_round("select round(x::numeric, 2) from t") == "select round(x::numeric, 2) from t"
    assert sql_agent.corriger_round("select 1") == "select 1"

"""
Charge le bronze (Parquet dans S3) dans PostgreSQL, schéma `raw`, sans transformation.

    python ingestion/load_postgres.py

Une table raw par jeu de données, toutes saisons et ligues réunies :
    raw.fbref_standard / fbref_shooting / fbref_misc / fbref_playing_time
    raw.understat_player_season
    raw.tm_players / tm_clubs / tm_competitions / tm_player_valuations ...
Rechargement complet à chaque exécution (table remplacée) : idempotent.
"""

from io import StringIO

import pandas as pd
from sqlalchemy import create_engine, text

from common import (journaliser, lire_parquet, lister_cles, pg_url, s3)

SCHEMA = "raw"


def regrouper(client, prefixe):
    """Lit tous les Parquet d'un préfixe et les empile (colonnes = union)."""
    cles = lister_cles(client, prefixe)
    if not cles:
        return None
    return pd.concat([lire_parquet(client, k).assign(_fichier=k) for k in cles],
                     ignore_index=True)


def copier(engine, df, table):
    """Remplace raw.<table> par df (création du schéma de table + COPY rapide)."""
    df = df.copy()
    df.columns = [c[:60] for c in df.columns]
    with engine.begin() as cx:
        cx.execute(text(f"create schema if not exists {SCHEMA}"))
        # cascade : les vues dbt qui dépendent de la table sont supprimées, `dbt run` les recrée
        cx.execute(text(f'drop table if exists {SCHEMA}."{table}" cascade'))
        df.head(0).to_sql(table, cx, schema=SCHEMA, if_exists="replace", index=False)
    buf = StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cols = ", ".join(f'"{c}"' for c in df.columns)
            cur.copy_expert(f'copy {SCHEMA}."{table}" ({cols}) from stdin with csv', buf)
        raw.commit()
    finally:
        raw.close()
    journaliser("postgres", f"{SCHEMA}.{table}", f"{SCHEMA}.{table}", len(df))


def main():
    client = s3()
    engine = create_engine(pg_url())
    with engine.begin() as cx:      # unaccent sert à normaliser les noms dans dbt
        cx.execute(text("create extension if not exists unaccent"))
    for table in ["standard", "shooting", "misc", "playing_time"]:
        df = regrouper(client, f"fbref/{table}/")
        if df is not None:
            copier(engine, df, f"fbref_{table}")
    df = regrouper(client, "understat/player_season/")
    if df is not None:
        copier(engine, df, "understat_player_season")
    for cle in lister_cles(client, "transfermarkt/"):
        table = cle.split("/")[-1].replace(".parquet", "")
        copier(engine, lire_parquet(client, cle), f"tm_{table}")
    print("\nTerminé : schéma raw rempli.")


if __name__ == "__main__":
    main()

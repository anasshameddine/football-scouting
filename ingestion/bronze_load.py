"""
Bronze, partie 1 : charge dans le bucket les fichiers DÉJÀ téléchargés (data/raw).

    python ingestion/bronze_load.py

Clés produites (Parquet) :
    fbref/<table>/saison=2025-2026/<ligue>.parquet
    understat/player_season/saison=2025-2026/<ligue>.parquet
    transfermarkt/<table>.parquet
Relancer le script réécrit les mêmes clés : pas de doublons.
"""

import pandas as pd

from common import (RAW, aplatir_fbref, assurer_bucket, ecrire_parquet,
                    s3, saison_longue, slug)

TABLES_FBREF = ["standard", "shooting", "misc", "playing_time"]
SAISON = "2025-2026"


def charger_fbref(client):
    print("\n== FBref ==")
    for table in TABLES_FBREF:
        fichiers = [RAW / f"{table}.csv"] + sorted((RAW / "extra").glob(f"*_{table}.csv"))
        df = pd.concat(
            [aplatir_fbref(pd.read_csv(f, header=[0, 1], index_col=[0, 1, 2, 3]))
             for f in fichiers if f.exists()], ignore_index=True)
        for ligue, sous in df.groupby("league"):
            saison = saison_longue(sous["season"].iloc[0])
            cle = f"fbref/{table}/saison={saison}/{slug(ligue)}.parquet"
            ecrire_parquet(client, sous, cle, "fbref", table)


def charger_understat(client):
    print("\n== Understat ==")
    f = RAW / "understat.csv"
    if not f.exists():
        print("  (understat.csv absent, ignoré)")
        return
    df = pd.read_csv(f)
    for ligue, sous in df.groupby("league"):
        saison = saison_longue(sous["season"].iloc[0])
        cle = f"understat/player_season/saison={saison}/{slug(ligue)}.parquet"
        ecrire_parquet(client, sous, cle, "understat", "player_season")


def charger_transfermarkt(client):
    print("\n== Transfermarkt ==")
    dossier = RAW / "transfermarkt"
    for f in sorted(dossier.glob("*.csv.gz")):
        table = f.name.replace(".csv.gz", "")
        df = pd.read_csv(f, low_memory=False)
        ecrire_parquet(client, df, f"transfermarkt/{table}.parquet", "transfermarkt", table)


if __name__ == "__main__":
    client = s3()
    assurer_bucket(client)
    charger_fbref(client)
    charger_understat(client)
    charger_transfermarkt(client)
    print("\nTerminé. Journal : data/logs/ingestion.jsonl")

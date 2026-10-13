"""
Bronze, partie 2 : collecte de nouvelles saisons et écriture directe dans le bucket.

    python ingestion/collect_bronze.py --source fbref --saisons 2024-2025 2023-2024
    python ingestion/collect_bronze.py --source understat --saisons 2024-2025
    python ingestion/collect_bronze.py --source fbref --saisons 2024-2025 --ligues NED-Eredivisie

Idempotent : une table déjà présente dans le bucket n'est pas retéléchargée
(ajouter --force pour la refaire). Une ligue qui échoue est notée dans le bilan
et n'arrête pas les autres. Le script peut être relancé autant de fois qu'on veut.
"""

import argparse

from leagues import BIG5, TOUTES, declarer_ligues_extra

declarer_ligues_extra()                      # avant d'importer soccerdata
import soccerdata as sd                      # noqa: E402

from common import (aplatir_fbref, assurer_bucket, ecrire_parquet, existe,  # noqa: E402
                    journaliser, s3, slug)

TABLES_FBREF = ["standard", "shooting", "misc", "playing_time"]


def collecter_fbref(client, ligue, saison, force, bilan):
    try:
        fbref = sd.FBref(leagues=[ligue], seasons=saison)
    except Exception as e:                    # ligue non reconnue
        bilan[(ligue, saison, "fbref")] = f"échec : {str(e)[:60]}"
        return
    for table in TABLES_FBREF:
        cle = f"fbref/{table}/saison={saison}/{slug(ligue)}.parquet"
        if existe(client, cle) and not force:
            print(f"  [déjà là] {cle}")
            continue
        try:
            df = aplatir_fbref(fbref.read_player_season_stats(stat_type=table))
            ecrire_parquet(client, df, cle, "fbref", table)
            bilan[(ligue, saison, table)] = f"{len(df)} lignes"
        except Exception as e:
            journaliser("fbref", table, cle, 0, statut="échec")
            bilan[(ligue, saison, table)] = f"échec : {str(e)[:60]}"


def collecter_understat(client, ligue, saison, force, bilan):
    if ligue not in BIG5:
        return                                # Understat : 5 grands championnats seulement
    cle = f"understat/player_season/saison={saison}/{slug(ligue)}.parquet"
    if existe(client, cle) and not force:
        print(f"  [déjà là] {cle}")
        return
    try:
        df = sd.Understat(leagues=[ligue], seasons=saison).read_player_season_stats()
        ecrire_parquet(client, df.reset_index(), cle, "understat", "player_season")
        bilan[(ligue, saison, "understat")] = f"{len(df)} lignes"
    except Exception as e:
        journaliser("understat", "player_season", cle, 0, statut="échec")
        bilan[(ligue, saison, "understat")] = f"échec : {str(e)[:60]}"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["fbref", "understat"], required=True)
    p.add_argument("--saisons", nargs="+", required=True, help="ex. 2024-2025")
    p.add_argument("--ligues", nargs="+", default=TOUTES)
    p.add_argument("--force", action="store_true")
    a = p.parse_args()

    client = s3()
    assurer_bucket(client)
    bilan = {}
    fonction = collecter_fbref if a.source == "fbref" else collecter_understat
    for saison in a.saisons:
        for ligue in a.ligues:
            print(f"\n=== {a.source} | {saison} | {ligue} ===")
            fonction(client, ligue, saison, a.force, bilan)

    print("\n=== BILAN ===")
    for (ligue, saison, table), r in bilan.items():
        print(f"{saison} {ligue:22s} {table:14s} {r}")

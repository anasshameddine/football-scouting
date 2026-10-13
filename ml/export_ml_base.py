"""
Exporte la table d'entraînement du modèle de valeur : une ligne par joueur et saison,
avec stats par 90 minutes, profil du joueur et valeur marchande en fin de saison.

    python ml/export_ml_base.py
Sortie : data/processed/ml_base.csv.gz (compressé, quelques Mo)
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))
from common import ROOT, pg_url  # noqa: E402

REQUETE = """
select f.*, p.player, p.born, p.nation_code, p.tm_player_id, p.tm_sub_position, p.tm_position,
       p.tm_foot, p.tm_height_cm, p.tm_citizenship, p.is_moroccan,
       p.tm_value_eur as valeur_actuelle_eur
from gold.fact_player_season f
join gold.dim_player p using (player_key)
"""

if __name__ == "__main__":
    sortie = ROOT / "data" / "processed" / "ml_base.csv.gz"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_sql(REQUETE, create_engine(pg_url()))
    df.to_csv(sortie, index=False, compression="gzip")
    print(f"{len(df)} lignes, {df.shape[1]} colonnes -> {sortie} "
          f"({sortie.stat().st_size / 1e6:.1f} Mo)")
    print(df.groupby("season")["valeur_fin_saison_eur"].agg(["count", "median"]))

"""
Exporte la table gold.mart_scouting (PostgreSQL) vers data/processed/joueurs_propres.csv.

    python ml/export_mart.py

Le dashboard et profiles.py lisent ce fichier : il peut donc tourner sans PostgreSQL
(par exemple une fois publié sur Streamlit Community Cloud).
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))
from common import ROOT, pg_url  # noqa: E402

if __name__ == "__main__":
    sortie = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "processed" / "joueurs_propres.csv"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_sql("select * from gold.mart_scouting order by league, team, player",
                     create_engine(pg_url()))
    df.to_csv(sortie, index=False)
    print(f"{len(df)} joueurs exportés vers {sortie}")

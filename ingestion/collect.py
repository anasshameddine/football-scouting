"""
Étape 1 — Collecte des données
Source : FBref via soccerdata
Saison : 2024-2025
Ligues  : Big 5 européennes
"""

import soccerdata as sd
from pathlib import Path

# ── Paramètres ─────────────────────────────────────────────────────────────
SAISON   = "2025-2026"
LIGUES   = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A",
            "GER-Bundesliga", "FRA-Ligue 1"]
OUT_DIR  = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Tables à récupérer ──────────────────────────────────────────────────────
TABLES = ["standard", "shooting", "playing_time", "misc"]

# ── Collecte ────────────────────────────────────────────────────────────────
fbref = sd.FBref(leagues=LIGUES, seasons=SAISON)

frames = []
for table in TABLES:
    print(f"Récupération : {table}...")
    try:
        df = fbref.read_player_season_stats(stat_type=table)
        df["_table"] = table
        frames.append(df)
        df.to_csv(OUT_DIR / f"{table}.csv")
        print(f"  → {len(df)} lignes sauvegardées dans data/raw/{table}.csv")
    except Exception as e:
        print(f"  ✗ Erreur sur {table} : {e}")

print("\nCollecte terminée.")
print(f"Fichiers dans : {OUT_DIR.resolve()}")

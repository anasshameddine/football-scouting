"""Championnats FBref : les 5 grands (natifs) et les ligues ajoutées à soccerdata."""

import json
import os
from pathlib import Path

BIG5 = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A",
        "GER-Bundesliga", "FRA-Ligue 1"]

EXTRA = {   # clé soccerdata -> nom FBref (les ligues absentes de la base ne répondent pas)
    "NED-Eredivisie": "Eredivisie",
    "POR-Primeira Liga": "Primeira Liga",
    "BEL-Pro League": "Belgian Pro League",
    "TUR-Super Lig": "Süper Lig",
    "SCO-Premiership": "Scottish Premiership",
    "AUT-Bundesliga": "Austrian Football Bundesliga",
    "SUI-Super League": "Swiss Super League",
    "DEN-Superliga": "Danish Superliga",
    "KSA-Pro League": "Saudi Pro League",
}
# FRA-Ligue 2 écartée (absente de Transfermarkt). Grèce, Championship, Serie B,
# 2. Bundesliga et Segunda ont échoué sur FBref lors du premier essai.

TOUTES = BIG5 + list(EXTRA)


def declarer_ligues_extra():
    """À appeler AVANT `import soccerdata` : écrit league_dict.json."""
    cfg_dir = Path(os.environ.get("SOCCERDATA_DIR", Path.home() / "soccerdata")) / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    fichier = cfg_dir / "league_dict.json"
    cfg = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
    for cle, nom in EXTRA.items():
        cfg[cle] = {"FBref": nom, "season_start": "Aug", "season_end": "May"}
    fichier.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

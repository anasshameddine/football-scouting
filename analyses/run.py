"""
Exécute les requêtes d'analyse de ce dossier sur PostgreSQL (schémas gold et ml)
et écrit un résumé dans docs/analyses_resultats.md.

    python analyses\run.py            # toutes les requêtes
    python analyses\run.py 03 08      # seulement celles dont le nom commence par 03 ou 08
"""

import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))
from common import pg_url  # noqa: E402

DOSSIER = Path(__file__).resolve().parent
SORTIE = ROOT / "docs" / "analyses_resultats.md"


def main(filtres):
    engine = create_engine(pg_url())
    fichiers = sorted(DOSSIER.glob("[0-9][0-9]_*.sql"))
    if filtres:
        fichiers = [f for f in fichiers if f.name[:2] in filtres]
    md = ["# Analyses SQL : résultats", "",
          f"Généré le {date.today()} par `analyses/run.py` sur le schéma gold (et ml pour la 06).", ""]
    for f in fichiers:
        sql = f.read_text(encoding="utf-8-sig")
        question = re.search(r"-- Question : (.+)", sql).group(1)
        technique = re.search(r"-- Technique : (.+)", sql).group(1)
        with engine.connect() as cx:
            df = pd.read_sql(text(sql), cx)
        print(f"\n=== {f.name}\n{question}\n{df.head(8).to_string(index=False)}")
        md += [f"## {f.stem}", "", f"**Question.** {question}  ", f"**Technique.** {technique}", "",
               df.head(10).to_markdown(index=False), "", f"[Requête]({f.name})", ""]
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text("\n".join(md), encoding="utf-8")
    print(f"\nRésumé écrit dans {SORTIE}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))

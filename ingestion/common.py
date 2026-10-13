"""
Outils communs de la couche bronze : configuration (.env), accès S3, écriture Parquet.

Principe d'idempotence : chaque jeu de données a une clé fixe dans le bucket
(source/table/saison/ligue). Relancer un script réécrit la même clé : aucun doublon.
"""

import json
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import boto3
import pandas as pd
from botocore.client import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LOG_FILE = ROOT / "data" / "logs" / "ingestion.jsonl"


def charger_env(chemin=ROOT / ".env"):
    """Lit .env (clé=valeur) sans dépendance ; les variables déjà définies gagnent."""
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                k, v = ligne.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


charger_env()


def s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "rustfsadmin"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "rustfsadmin"),
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


BUCKET = os.environ.get("S3_BUCKET", "bronze")


def assurer_bucket(client):
    try:
        client.head_bucket(Bucket=BUCKET)
    except ClientError:
        client.create_bucket(Bucket=BUCKET)


def existe(client, cle):
    try:
        client.head_object(Bucket=BUCKET, Key=cle)
        return True
    except ClientError:
        return False


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def saison_longue(s):
    """'2526' -> '2025-2026' ; '2025-2026' reste inchangé."""
    s = str(s)
    if re.fullmatch(r"\d{4}", s):
        return f"20{s[:2]}-20{s[2:]}"
    return s


def journaliser(source, table, cle, lignes, statut="ok"):
    """Une ligne JSON par écriture : date, source, table, clé, nombre de lignes."""
    evt = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": source, "table": table, "cle": cle, "lignes": int(lignes),
           "statut": statut}
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    print(f"  [{statut}] {cle} : {lignes} lignes")


def ecrire_parquet(client, df, cle, source, table):
    """Écrit un DataFrame en Parquet à la clé donnée (écrase : idempotent)."""
    df = df.copy()
    df["_ingere_le"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    buf = BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    client.put_object(Bucket=BUCKET, Key=cle, Body=buf.getvalue())
    journaliser(source, table, cle, len(df))


def lire_parquet(client, cle):
    obj = client.get_object(Bucket=BUCKET, Key=cle)
    return pd.read_parquet(BytesIO(obj["Body"].read()))


# --- en-têtes FBref (deux niveaux) aplatis en noms simples --------------------
KEYS = ["league", "season", "team", "player"]


def nettoyer_nom_colonne(c):
    c = str(c).lower().strip()
    for a, b in [("%", "_pct"), ("/", "_per_"), ("+", "_plus_"), ("-", "_minus_"),
                 (":", "_"), (" ", "_")]:
        c = c.replace(a, b)
    while "__" in c:
        c = c.replace("__", "_")
    return c.strip("_")


def aplatir_fbref(df):
    """DataFrame à colonnes MultiIndex (soccerdata) -> colonnes simples + clés en colonnes."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        cols = []
        for haut, bas in df.columns:
            haut = "" if str(haut).startswith("Unnamed") else str(haut)
            bas = "" if str(bas).startswith("Unnamed") else str(bas)
            cols.append(f"{haut}_{bas}" if (haut and bas) else (haut or bas))
        df.columns = [nettoyer_nom_colonne(c) for c in cols]
    else:
        df.columns = [nettoyer_nom_colonne(c) for c in df.columns]
    df = df.drop(columns=[c for c in df.columns if c == "table"], errors="ignore")
    if df.index.nlevels > 1 or df.index.name:
        df.index.names = KEYS[:df.index.nlevels] if df.index.nlevels == 4 else df.index.names
        df = df.reset_index()
    return df


# --- PostgreSQL -----------------------------------------------------------------
def pg_url():
    return ("postgresql+psycopg2://{u}:{p}@{h}:{port}/{d}".format(
        u=os.environ.get("POSTGRES_USER", "scout"),
        p=os.environ.get("POSTGRES_PASSWORD", "scout_dev_password"),
        h=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5433"),
        d=os.environ.get("POSTGRES_DB", "scouting")))


def lister_cles(client, prefixe):
    pages = client.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefixe)
    return sorted(o["Key"] for p in pages for o in p.get("Contents", []))

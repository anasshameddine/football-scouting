"""Réglages de l'assistant, modifiables dans .env sans toucher au code."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))
from common import pg_url  # noqa: E402  (charge aussi .env)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODELE = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")            # génération (SQL, réponses, rapports)
MODELE_EMBED = os.environ.get("OLLAMA_EMBED_MODEL", "bge-m3")    # embeddings multilingues (RAG)
# Connexion en lecture seule conseillée pour l'agent SQL (voir assistant/sql/role_lecture.sql).
DB_URL_LECTURE = os.environ.get("ASSISTANT_DB_URL") or pg_url()
DB_URL = pg_url()
MAX_LIGNES = 200          # lignes renvoyées au maximum par une requête générée
TIMEOUT_SQL_MS = 10_000   # une requête générée ne peut pas tourner plus de 10 s

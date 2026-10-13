"""
Client minimal pour Ollama (modèles exécutés en local, gratuits, sans clé).

    chat([{"role": "user", "content": "Bonjour"}])  ->  "Bonjour ! ..."
    embed(["texte 1", "texte 2"])                   ->  [[0.01, ...], [...]]
"""

import requests

from .config import MODELE, MODELE_EMBED, OLLAMA_URL


class OllamaIndisponible(RuntimeError):
    """Ollama n'est pas lancé, ou le modèle demandé n'est pas téléchargé."""


def _post(chemin, corps, timeout):
    try:
        r = requests.post(f"{OLLAMA_URL}{chemin}", json=corps, timeout=timeout)
    except requests.ConnectionError as e:
        raise OllamaIndisponible(
            f"Ollama ne répond pas sur {OLLAMA_URL}. Lance l'application Ollama "
            "(ou « ollama serve ») puis réessaie.") from e
    if r.status_code == 404 and "not found" in r.text:
        raise OllamaIndisponible(
            f"Modèle « {corps.get('model')} » absent. Télécharge-le : ollama pull {corps.get('model')}")
    r.raise_for_status()
    return r.json()


def chat(messages, modele=None, temperature=0.0, timeout=300):
    """Réponse complète du modèle (pas de streaming). Température 0 : résultats reproductibles."""
    d = _post("/api/chat", {"model": modele or MODELE, "messages": messages, "stream": False,
                            "options": {"temperature": temperature, "num_ctx": 8192}}, timeout)
    return d["message"]["content"]


def embed(textes, modele=None, timeout=300):
    """Un vecteur par texte."""
    d = _post("/api/embed", {"model": modele or MODELE_EMBED, "input": list(textes)}, timeout)
    return d["embeddings"]


def etat(modeles=None):
    """(ok, message) : Ollama lancé et modèles présents ?"""
    modeles = modeles or (MODELE, MODELE_EMBED)
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
    except requests.RequestException:
        return False, f"Ollama ne répond pas sur {OLLAMA_URL}."
    presents = {m["name"] for m in r.json().get("models", [])}
    presents |= {n.split(":")[0] for n in presents if n.endswith(":latest")}
    manquants = [m for m in modeles if m not in presents]
    if manquants:
        return False, "Modèle(s) à télécharger : " + ", ".join(f"ollama pull {m}" for m in manquants)
    return True, f"Ollama prêt ({', '.join(modeles)})."

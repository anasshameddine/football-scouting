"""
Biographie et photo d'un joueur depuis Wikipédia (API publique, gratuite, sans clé).

Une seule requête par joueur : la recherche renvoie directement, pour les 5 meilleures pages,
le résumé, la description, l'adresse et la miniature (moins de requêtes = pas de blocage « 429 »).
La photo n'est pas téléchargée : on garde son adresse et le navigateur la charge depuis Wikimedia.
Les homonymes sont écartés en vérifiant que la page parle d'un footballeur et que l'année
de naissance ou le club du joueur apparaît dans le résumé.

    chercher("Azzedine Ounahi", 2000, "fr")  ->  {"titre", "description", "extrait", "url", "image"} ou None
"""

import os
import unicodedata

import requests

MOTS_FOOT = {"en": ("footballer", "football player", "soccer"),
             "fr": ("footballeur", "footballeuse")}


def ua():
    """Wikimedia demande un User-Agent qui permet de contacter l'auteur : mettre son e-mail ou
    l'adresse du dépôt GitHub dans WIKI_CONTACT (.env). Sans contact, les limites sont plus strictes."""
    contact = os.environ.get("WIKI_CONTACT", "student data project")
    return {"User-Agent": f"ScoutingFootballPortfolio/1.0 ({contact}) python-requests"}


def _norm(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def _json(url, params=None, get=requests.get):
    r = get(url, params=params, headers=ua(), timeout=8)
    r.raise_for_status()
    return r.json()


def _footballeur(p, lang):
    texte = (p.get("description", "") + " " + p.get("extract", "")).lower()
    return any(m in texte for m in MOTS_FOOT[lang])


def _format(p):
    return {"titre": p.get("title"), "description": p.get("description", ""),
            "extrait": p.get("extract", ""), "url": p.get("fullurl"),
            "image": (p.get("thumbnail") or {}).get("source")}


def candidats(nom, lang, get=requests.get):
    """Les 5 premières pages de la recherche « nom footballeur », avec résumé et miniature."""
    d = _json(f"https://{lang}.wikipedia.org/w/api.php", {
        "action": "query", "format": "json", "formatversion": 2, "redirects": 1,
        "generator": "search", "gsrsearch": f"{nom} {MOTS_FOOT[lang][0]}", "gsrlimit": 5,
        "prop": "extracts|description|pageimages|info|pageprops",
        "exintro": 1, "explaintext": 1, "exlimit": "max",
        "piprop": "thumbnail", "pithumbsize": 320, "inprop": "url", "ppprop": "disambiguation"}, get)
    pages = d.get("query", {}).get("pages", [])
    return sorted(pages, key=lambda p: p.get("index", 99))


def chercher(nom, born, lang, club=None, get=requests.get, lever=False):
    """Meilleure page plausible, ou None (page absente, homonyme douteux, réseau indisponible).
    Score : année de naissance dans le résumé (2) + club cité (1) + titre identique au nom (0,5).
    lever=True : une erreur réseau lève une exception au lieu de renvoyer None
    (l'indexation ne doit pas confondre « pas de page » et « pas de connexion »)."""
    try:
        pages = candidats(nom, lang, get)
    except (requests.RequestException, KeyError, ValueError):
        if lever:
            raise
        return None
    annee = str(int(born)) if born is not None and born == born else None
    club_n = _norm(club) if club else None
    meilleur, score_max = None, 0
    for p in pages:
        if "disambiguation" in (p.get("pageprops") or {}) or not _footballeur(p, lang):
            continue
        texte = p.get("description", "") + " " + p.get("extract", "")
        score = ((2 if annee and annee in texte else 0)
                 + (1 if club_n and club_n in _norm(texte) else 0)
                 + (0.5 if _norm(p.get("title", "").split(" (")[0]) == _norm(nom) else 0))
        if score > score_max:
            meilleur, score_max = p, score
    # Un titre identique ne suffit pas (homonymes) : il faut l'année de naissance ou le club.
    # Sans année ni club connus, on accepte le titre identique faute de mieux.
    seuil = 1 if (annee or club_n) else 0.5
    return _format(meilleur) if meilleur and score_max >= seuil else None

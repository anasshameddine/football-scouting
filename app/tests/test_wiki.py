"""Tests de la recherche Wikipédia, sans réseau (réponses simulées)."""
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wiki  # noqa: E402


class Rep:
    def __init__(self, data, code=200):
        self.data, self.status_code = data, code

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError("erreur")

    def json(self):
        return self.data


PAGES = [
    {"index": 1, "title": "Vitinha", "description": "Portuguese footballer",
     "extract": "Vítor Ferreira (born 13 February 2000) plays for Paris Saint-Germain.",
     "fullurl": "https://en.wikipedia.org/wiki/Vitinha",
     "thumbnail": {"source": "https://upload.wikimedia.org/psg.jpg"}},
    {"index": 2, "title": "Vitinha (footballer, born March 2000)", "description": "Portuguese footballer",
     "extract": "Vítor Oliveira (born 15 March 2000) is a footballer who plays for Genoa."},
    {"index": 3, "title": "Vitinha (disambiguation)", "pageprops": {"disambiguation": ""},
     "extract": "Vitinha may refer to: Vitinha (footballer, born 2000)..."},
]


def faux(url, params=None, headers=None, timeout=None):
    assert "w/api.php" in url and params["generator"] == "search"
    return Rep({"query": {"pages": PAGES if "Vitinha" in params["gsrsearch"] else []}})


def test_homonyme_departage_par_le_club():
    assert wiki.chercher("Vitinha", 2000, "en", club="Genoa", get=faux)["titre"].endswith("March 2000)")
    assert wiki.chercher("Vitinha", 2000, "en", club="Paris", get=faux)["titre"] == "Vitinha"


def test_image_url_et_page_absente():
    r = wiki.chercher("Vitinha", 2000, "en", club="Paris", get=faux)
    assert r["image"].endswith("psg.jpg") and r["url"].endswith("/Vitinha")
    assert wiki.chercher("Joueur Inconnu", 1990, "en", get=faux) is None


def test_reseau_indisponible():
    def panne(*a, **k):
        raise requests.ConnectionError()
    assert wiki.chercher("Vitinha", 2000, "fr", get=panne) is None
    with pytest.raises(requests.ConnectionError):
        wiki.chercher("Vitinha", 2000, "fr", get=panne, lever=True)


def test_homonyme_d_une_autre_annee_est_rejete():
    """Même nom, mais ni l'année de naissance ni le club ne correspondent : pas de biographie."""
    assert wiki.chercher("Vitinha", 1992, "en", club="Rayo Vallecano", get=faux) is None

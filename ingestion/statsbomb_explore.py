"""
Exploration de StatsBomb Open Data (https://github.com/statsbomb/open-data) pour le projet.

    python ingestion/statsbomb_explore.py

Ce que fait le script :
1. liste les compétitions gratuites et repère celles où des joueurs marocains apparaissent dans les compositions ;
2. écrit la liste de ces joueurs (docs/statsbomb_marocains.csv) ;
3. sur les matchs du Maroc, calcule des statistiques par joueur à partir des événements (tirs, xG, passes...) ;
4. si data/processed/joueurs_propres.csv existe, indique combien de ces joueurs sont déjà dans notre base ;
5. écrit le bilan dans docs/statsbomb_exploration.md.

Les fichiers téléchargés sont gardés dans data/raw/statsbomb : relancer ne retélécharge rien.
Licence : citer StatsBomb comme source et afficher leur logo si les résultats sont publiés
(https://statsbomb.com/media-pack/).
"""

import concurrent.futures as cf
import json
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from unidecode import unidecode

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "statsbomb"
DOCS = ROOT / "docs"
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/"
UA = {"User-Agent": "scouting-portfolio (projet etudiant)"}


def get(chemin):
    """JSON de StatsBomb, avec cache disque. None si le fichier n'existe pas."""
    f = CACHE / chemin
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    for _ in range(3):
        try:
            req = urllib.request.Request(BASE + chemin, headers=UA)
            texte = urllib.request.urlopen(req, timeout=40).read().decode("utf-8")
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(texte, encoding="utf-8")
            return json.loads(texte)
        except Exception:
            continue
    return None


def telecharger(chemins):
    with cf.ThreadPoolExecutor(12) as ex:
        return dict(zip(chemins, ex.map(get, chemins)))


def joueurs_marocains():
    comps = get("competitions.json")
    matchs = {}
    for c in comps:
        m = get(f"matches/{c['competition_id']}/{c['season_id']}.json") or []
        for x in m:
            matchs[x["match_id"]] = (f"{c['competition_name']} {c['season_name']}", x)
    compos = telecharger([f"lineups/{i}.json" for i in matchs])
    joueurs = {}
    for chemin, equipes in compos.items():
        mid = int(chemin.split("/")[1].split(".")[0])
        comp, m = matchs[mid]
        for eq in equipes or []:
            for p in eq["lineup"]:
                if (p.get("country") or {}).get("name") != "Morocco":
                    continue
                j = joueurs.setdefault(p["player_id"], {
                    "player_id": p["player_id"], "joueur": p["player_name"], "surnom": p.get("player_nickname"),
                    "equipes": set(), "competitions": Counter(), "matchs_maroc": set()})
                j["equipes"].add(eq["team_name"])
                j["competitions"][comp] += 1
                if eq["team_name"] == "Morocco":
                    j["matchs_maroc"].add(mid)
    return comps, matchs, joueurs


def stats_evenements(matchs_maroc, matchs):
    """Statistiques par joueur sur les matchs du Maroc, à partir des événements."""
    evts = telecharger([f"events/{i}.json" for i in matchs_maroc])
    lignes = defaultdict(Counter)
    for chemin, evs in evts.items():
        for e in evs or []:
            if (e.get("team") or {}).get("name") != "Morocco" or "player" not in e:
                continue
            j = e["player"]["name"]
            t = e["type"]["name"]
            s = lignes[j]
            if t == "Shot":
                s["tirs"] += 1
                s["xg"] += e["shot"].get("statsbomb_xg", 0)
                s["buts"] += e["shot"]["outcome"]["name"] == "Goal"
            elif t == "Pass":
                s["passes"] += 1
                s["passes_reussies"] += "outcome" not in e["pass"]
                s["passes_cles"] += "shot_assist" in e["pass"] or "goal_assist" in e["pass"]
            elif t == "Pressure":
                s["pressions"] += 1
            elif t == "Duel" and e.get("duel", {}).get("type", {}).get("name") == "Tackle":
                s["tacles"] += 1
            elif t == "Interception":
                s["interceptions"] += 1
            elif t == "Carry":
                s["conduites"] += 1
            elif t == "Dribble":
                s["dribbles"] += 1
    df = pd.DataFrame(lignes).T.fillna(0).astype(float)
    df["xg"] = df["xg"].round(2)
    return df.sort_values("passes", ascending=False)


def jetons(nom):
    return set(unidecode(str(nom)).lower().replace("-", " ").split())


def recouvrement(joueurs):
    """Joueurs StatsBomb déjà dans notre base (noms comparés sans accents, jetons inclus l'un dans l'autre)."""
    f = ROOT / "data" / "processed" / "joueurs_propres.csv"
    if not f.exists():
        return None
    base = pd.read_csv(f)
    col = "player_clean" if "player_clean" in base else "player"
    notres = [(n, jetons(n)) for n in base[col].dropna().unique()]
    trouves = {}
    for j in joueurs.values():
        a = jetons(j["joueur"]) | jetons(j["surnom"] or "")
        for n, b in notres:
            if len(b) >= 2 and (b <= a or (len(a) >= 2 and a <= b)):
                trouves[j["joueur"]] = n
                break
    return trouves


def main():
    comps, matchs, joueurs = joueurs_marocains()
    DOCS.mkdir(exist_ok=True)
    lignes = [{"joueur": j["joueur"], "surnom": j["surnom"], "equipes": " / ".join(sorted(j["equipes"])),
               "matchs_maroc": len(j["matchs_maroc"]),
               "compositions": sum(j["competitions"].values()),
               "competitions": " ; ".join(f"{c} ({n})" for c, n in j["competitions"].most_common())}
              for j in joueurs.values()]
    liste = pd.DataFrame(lignes).sort_values(["matchs_maroc", "compositions"], ascending=False)
    liste.to_csv(DOCS / "statsbomb_marocains.csv", index=False, encoding="utf-8")

    maroc = {i for i, (_, m) in matchs.items() if "Morocco" in (m["home_team"]["home_team_name"],
                                                                m["away_team"]["away_team_name"])}
    par_comp = Counter(matchs[i][0] for i in maroc)
    stats = stats_evenements(maroc, matchs)
    stats.to_csv(DOCS / "statsbomb_stats_maroc.csv", encoding="utf-8")
    commun = recouvrement(joueurs)

    md = [f"# StatsBomb Open Data : exploration ({date.today():%d/%m/%Y})", "",
          "Source : [StatsBomb Open Data](https://github.com/statsbomb/open-data). Si ces données sont publiées ou "
          "présentées, il faut citer StatsBomb comme source et afficher leur logo "
          "([media pack](https://statsbomb.com/media-pack/)).", "",
          "## Ce qui est disponible", "",
          f"- {len(comps)} saisons de compétitions gratuites, {len(matchs)} matchs avec compositions.",
          "- Données d'événements (chaque passe, tir, pression, conduite de balle) avec position sur le terrain, "
          "et xG de StatsBomb pour chaque tir.",
          "- Ce n'est pas une saison complète des grands championnats : seules quelques saisons et compétitions "
          "sont ouvertes, souvent un seul club (Leverkusen 2023-24, Barça en Liga...).", "",
          "## Joueurs marocains",
          "", f"{len(joueurs)} joueurs de nationalité marocaine apparaissent dans les compositions "
          "(liste complète : `docs/statsbomb_marocains.csv`). La nationalité est celle indiquée par StatsBomb : elle inclut des binationaux qui jouent pour un autre pays (ex. Munir El Haddadi).", "",
          "Matchs du Maroc couverts :", ""]
    md += [f"- {c} : {n} matchs" for c, n in par_comp.most_common()]
    md += ["", "Les joueurs les plus présents :", "", liste.head(15)[["joueur", "matchs_maroc", "equipes"]]
           .to_markdown(index=False), "",
           "## Statistiques par joueur sur les matchs du Maroc (événements)", "",
           stats.head(12).to_markdown(), "",
           "Colonnes : tirs, xG (somme des xG StatsBomb), passes (réussies, clés), pressions, tacles, "
           "interceptions, conduites de balle, dribbles. Calcul sur 14 matchs du Maroc au plus par joueur.", ""]
    if commun is not None:
        md += ["## Recoupement avec notre base", "",
               f"{len(commun)} joueurs StatsBomb sur {len(joueurs)} sont déjà dans `joueurs_propres.csv`.", ""]
    md += ["## Verdict", "",
           "- **Utile** : fiches avec carte des tirs, xG réel par tir et réseau de passes de l'équipe nationale "
           "(Coupe du monde 2018 et 2022, CAN 2023). Donnée de bien meilleure qualité que FBref pour le détail.",
           "- **Limite** : 3 tournois seulement (14 matchs du Maroc au plus par joueur), pas de saison de club complète pour les "
           "Marocains. Impossible d'alimenter le modèle de valeur ni les percentiles de saison.",
           "- **Choix** : source complémentaire, affichée dans la fiche joueur quand elle existe, jamais mélangée "
           "aux statistiques de saison. Indiquer clairement « équipe nationale, tournois uniquement »."]
    (DOCS / "statsbomb_exploration.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:30]))


if __name__ == "__main__":
    main()

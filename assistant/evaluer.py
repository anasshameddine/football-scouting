"""
Mesure la précision de l'agent texte vers SQL sur les 20 questions de test.

Une réponse est juste si elle renvoie les mêmes données que la requête de référence :
même nombre de lignes, et chaque colonne de la référence se retrouve dans le résultat
(les colonnes en plus sont tolérées, les montants affichés en millions aussi).

    python -m assistant.evaluer            # écrit docs/assistant_evaluation.md
    python -m assistant.evaluer 2 8 13     # seulement certaines questions
"""

import sys
import time
from datetime import date

import numpy as np
import pandas as pd

from . import llm, sql_agent
from .config import DB_URL, MODELE, ROOT
from .questions_test import QUESTIONS, QUESTIONS_NOUVELLES

SORTIE = ROOT / "docs" / "assistant_evaluation.md"


def _colonne(s):
    """Valeurs normalisées d'une colonne : nombres en float, textes en minuscules."""
    num = pd.to_numeric(s, errors="coerce")
    if s.notna().sum() and num.notna().sum() == s.notna().sum():
        return "num", num.astype(float).to_numpy()
    return "txt", np.array([str(x).strip().lower() if pd.notna(x) else "" for x in s])


def _egales(a, b, ordonne):
    (ta, va), (tb, vb) = a, b
    if ta != tb or len(va) != len(vb):
        return False
    if ta == "txt":
        return list(va) == list(vb) if ordonne else sorted(va) == sorted(vb)
    if not ordonne:
        va, vb = np.sort(va), np.sort(vb)
    for echelle in (1, 1e6, 1e-6, 100, 0.01):        # euros / millions, ratio / pourcentage
        if np.allclose(va, vb * echelle, rtol=0.02, atol=0.06, equal_nan=True):
            return True
    return False


def meme_resultat(ref, pred, ordonne=False):
    """True si chaque colonne de la référence a une colonne équivalente dans le résultat."""
    if pred is None or len(ref) != len(pred):
        return False
    cols_pred = [_colonne(pred.iloc[:, j]) for j in range(pred.shape[1])]
    for i in range(ref.shape[1]):
        c = _colonne(ref.iloc[:, i])
        # pour un classement, les ex aequo peuvent changer l'ordre des noms : textes comparés sans ordre
        if not any(_egales(c, p, ordonne and c[0] == "num") for p in cols_pred):
            return False
    return True


def evaluer(ids=None, db_url=None, chat=None):
    db_url = db_url or DB_URL
    _, valeurs = sql_agent.contexte(db_url)
    lignes = []
    for q in QUESTIONS + QUESTIONS_NOUVELLES:
        if ids and q["id"] not in ids:
            continue
        ref, _ = sql_agent.executer(q["sql"].format(derniere=valeurs["derniere"]), db_url)
        t0 = time.time()
        rep = sql_agent.generer_et_executer(q["question"], db_url, chat)
        duree = time.time() - t0
        ok = rep.erreur is None and meme_resultat(ref, rep.donnees, q["ordonne"])
        lignes.append({"id": q["id"], "question": q["question"], "juste": ok,
                       "jeu": "nouvelles" if q in QUESTIONS_NOUVELLES else "mise au point",
                       "essais": len(rep.essais) + (rep.erreur is None), "secondes": round(duree, 1),
                       "erreur": rep.erreur, "sql": rep.sql})
        print(f"{q['id']:>2} {'OK ' if ok else 'NON'} {duree:5.1f}s  {q['question']}")
        if not ok:
            print("     requête :", " ".join((rep.sql or "aucune").split())[:230])
            print("     attendu :", ref.head(3).values.tolist())
            print("     obtenu  :", rep.donnees.head(3).values.tolist() if rep.donnees is not None
                  else (rep.erreur or "")[:100])
    return pd.DataFrame(lignes)


def ecrire(res):
    n, justes = len(res), int(res["juste"].sum())
    scores = []
    for jeu, titre in [("mise au point", "Questions 1-20 (règles du prompt ajustées sur leurs erreurs)"),
                       ("nouvelles", "Questions 21-30 (jamais vues pendant la mise au point)")]:
        r = res[res["jeu"] == jeu]
        if len(r):
            scores.append(f"- {titre} : **{int(r['juste'].sum())} / {len(r)}**")
            print(f"{titre} : {int(r['juste'].sum())}/{len(r)}")
    md = ["# Assistant : précision de l'agent texte vers SQL", "",
          f"Modèle : `{MODELE}` (Ollama, local). Date : {date.today():%d/%m/%Y}.", "",
          f"**{justes} / {n} réponses justes ({justes / n:.0%})**, "
          f"temps médian {res['secondes'].median():.0f} s par question.", "", *scores, "",
          "Le score des questions 21-30 est le plus honnête : le prompt n'a pas été corrigé en les regardant.", "",
          "Une réponse est juste si elle renvoie les mêmes données que la requête de référence "
          "(colonnes en plus tolérées, montants en millions acceptés).", "",
          "| # | Question | Juste | Essais | Temps (s) |", "|---|---|---|---|---|"]
    for r in res.itertuples():
        md.append(f"| {r.id} | {r.question} | {'oui' if r.juste else 'non'} | {r.essais} | {r.secondes} |")
    md += ["", "## Requêtes générées", ""]
    for r in res.itertuples():
        md += [f"**{r.id}. {r.question}** ({'juste' if r.juste else 'fausse'})", "",
               "```sql", (r.sql or "-- aucune requête").strip(), "```", ""]
        if r.erreur:
            md += [f"Erreur : {r.erreur}", ""]
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text("\n".join(md), encoding="utf-8")
    print(f"\n{justes}/{n} justes -> {SORTIE}")


if __name__ == "__main__":
    ok, msg = llm.etat([MODELE])
    if not ok:
        sys.exit(msg)
    ecrire(evaluer({int(x) for x in sys.argv[1:]} or None))

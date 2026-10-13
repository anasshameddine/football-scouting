"""
Compare les méthodes de similarité sur un test objectif : retrouver un joueur d'une saison à l'autre.

Principe : pour chaque joueur présent en saison N et N-1 (au moins 900 minutes), on classe tous les
joueurs du même poste en N-1 selon leur proximité avec son profil de la saison N. Un bon profil
statistique doit remettre le joueur lui-même en tête (son style change peu d'une année à l'autre).
Mesures : hit@1 / hit@5 / hit@10 (part de joueurs retrouvés dans les k premiers) et MRR.
Le hasard donnerait environ k / taille du bassin (de l'ordre de 1 % pour k = 10).

    python ml\\similarity_eval.py      ->  docs\\similarite_comparaison.md
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import P90_FBREF, P90_UNDERSTAT  # noqa: E402
from profiles import (BIG5, FBREF_VERS_GROUPE, METRIQUES, SUB_VERS_GROUPE, TOUTES,  # noqa: E402
                      metriques)

ROOT = Path(__file__).resolve().parents[1]
PAIRES = [("2425", "2526"), ("2324", "2425"), ("2223", "2324")]
METHODES = ["percentiles + euclid", "percentiles + cosinus", "z-scores + euclid",
            "ACP + euclid", "ACP + cosinus"]


def embeddings(Xs, methode):
    """Xs : {saison: DataFrame de stats}. Renvoie {saison: matrice}."""
    if methode.startswith("percentiles"):
        return {s: X.rank(pct=True).values for s, X in Xs.items()}
    Z = {s: ((X - X.mean()) / X.std(ddof=0)).clip(-3, 3) for s, X in Xs.items()}
    if methode.startswith("z-scores"):
        return {s: z.values for s, z in Z.items()}
    p = PCA(n_components=0.9, svd_solver="full").fit(pd.concat(Z.values()))
    return {s: p.transform(z) for s, z in Z.items()}


def distances(A, B, cosinus):
    if cosinus:
        A = A / np.linalg.norm(A, axis=1, keepdims=True)
        B = B / np.linalg.norm(B, axis=1, keepdims=True)
        return 1 - A @ B.T
    return np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(2))


def evaluer(df, colonnes_par_groupe):
    rangs = {m: [] for m in METHODES}
    bassins = []
    for g, cols in colonnes_par_groupe.items():
        for sa, sb in PAIRES:
            a = df[(df["groupe"] == g) & (df["season"] == sa)].dropna(subset=cols).drop_duplicates("player_key")
            b = df[(df["groupe"] == g) & (df["season"] == sb)].dropna(subset=cols).drop_duplicates("player_key")
            communs = set(a["player_key"]) & set(b["player_key"])
            if len(communs) < 30:
                continue
            cles = a["player_key"].values
            bassins.append(len(a))
            for m in METHODES:
                E = embeddings({sa: a[cols], sb: b[cols]}, m)
                D = distances(E[sb], E[sa], m.endswith("cosinus"))
                for i, pk in enumerate(b["player_key"].values):
                    if pk in communs:
                        ordre = np.argsort(D[i])
                        rangs[m].append(int(np.where(cles[ordre] == pk)[0][0]) + 1)
    lignes = {}
    for m, r in rangs.items():
        r = np.array(r)
        lignes[m] = {"hit@1 (%)": (r == 1).mean() * 100, "hit@5 (%)": (r <= 5).mean() * 100,
                     "hit@10 (%)": (r <= 10).mean() * 100, "MRR": (1 / r).mean(), "joueurs testés": len(r)}
    hasard = 10 / np.mean(bassins) * 100
    return pd.DataFrame(lignes).T.round(2), hasard


def main():
    df = pd.read_csv(ROOT / "data" / "processed" / "ml_base.csv.gz", low_memory=False,
                     dtype={"season": str})
    df = df[(df["pos_main"] != "GK") & (df["playing_time_min"] >= 900)].copy()
    df["groupe"] = df["tm_sub_position"].map(SUB_VERS_GROUPE).fillna(df["pos_main"].map(FBREF_VERS_GROUPE))
    df = df[df["groupe"].notna()]
    big5 = df[df["league"].isin(BIG5) & df["us_xg_p90"].notna()]

    scenarios = [
        ("A. 14 championnats, métriques du poste (FBref)", df,
         {g: [TOUTES[n] for n in metriques(g, "all")] for g in METRIQUES}),
        ("B. 5 grands championnats, métriques du poste (FBref + Understat)", big5,
         {g: [TOUTES[n] for n in metriques(g, "big5")] for g in METRIQUES}),
        ("C. 5 grands championnats, 17 statistiques pour tous les postes", big5,
         {g: P90_FBREF + P90_UNDERSTAT for g in METRIQUES}),
    ]
    md = ["# Comparaison des méthodes de similarité", "",
          f"Généré le {date.today()} par `ml/similarity_eval.py`.", "",
          "Test : retrouver un joueur d'une saison à l'autre parmi les joueurs du même poste "
          "(voir l'en-tête du script). Plus c'est haut, mieux la méthode capte le style d'un joueur.", ""]
    for titre, base, cols in scenarios:
        t, hasard = evaluer(base, cols)
        print(f"\n{titre}\n{t}\n(hasard : hit@10 de l'ordre de {hasard:.1f} %)")
        md += [f"## {titre}", "", t.to_markdown(), "", f"Hasard : hit@10 de l'ordre de {hasard:.1f} %.", ""]
    md += ["## Lecture", "",
           "- Les méthodes sont proches (1 à 2 points d'écart) et toutes très au-dessus du hasard. "
           "L'ACP ne bat ni les percentiles ni les z-scores : avec 5 à 17 statistiques, réduire la dimension apporte peu.",
           "- Les z-scores en distance euclidienne ont un léger avantage sur hit@1 ; les percentiles font aussi bien sur hit@10.",
           "- Ce qui améliore le plus le résultat, c'est le nombre de statistiques (scénario C).",
           "- Le cosinus est moins bon que la distance euclidienne : l'intensité du profil compte, pas seulement sa forme.",
           "- Le dashboard garde les percentiles par défaut (score borné de 0 à 100, lisible, robuste aux valeurs extrêmes) "
           "et propose l'ACP + plus proches voisins comme variante."]
    out = ROOT / "docs" / "similarite_comparaison.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"\nÉcrit dans {out}")


if __name__ == "__main__":
    main()

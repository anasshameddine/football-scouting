"""
Étape 3 — Métriques, profils (archétypes) et recherche de joueurs similaires.

Principe
- Chaque joueur est rangé dans un GROUPE DE POSTE (6 groupes).
- Pour chaque groupe, on choisit les métriques qui comptent (par 90 minutes).
- Chaque métrique est convertie en PERCENTILE dans son groupe (0 = le plus faible,
  1 = le meilleur). Ça rend les métriques comparables entre elles.
- Similarité = distance entre les vecteurs de percentiles, ramenée sur 100.
- Deux modes :
    "big5"  -> 5 grands championnats, métriques FBref + Understat (xG, xA...)
    "all"   -> 14 championnats, métriques FBref uniquement (présentes partout)

Usage rapide
    from profiles import charger_base, similaires
    df = charger_base()
    print(similaires(df, "Jeremy Doku", mode="all"))
"""

from pathlib import Path
import numpy as np
import pandas as pd
from unidecode import unidecode

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "joueurs_propres.csv"

BIG5 = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A",
        "GER-Bundesliga", "FRA-Ligue 1"]

# 1. Groupes de poste (poste précis Transfermarkt, sinon poste FBref) --------
SUB_VERS_GROUPE = {
    "Centre-Back": "Défenseur central",
    "Left-Back": "Latéral", "Right-Back": "Latéral",
    "Defensive Midfield": "Milieu", "Central Midfield": "Milieu",
    "Attacking Midfield": "Milieu offensif",
    "Left Winger": "Ailier", "Right Winger": "Ailier",
    "Left Midfield": "Ailier", "Right Midfield": "Ailier",
    "Centre-Forward": "Attaquant", "Second Striker": "Attaquant",
}
FBREF_VERS_GROUPE = {"DF": "Défenseur central", "MF": "Milieu", "FW": "Attaquant"}

# 2. Métriques par groupe : {nom court: colonne} ------------------------------
M = {  # FBref, disponibles dans les 14 championnats
    "buts_hors_pen": "performance_g_minus_pk_p90",
    "passes_dec": "performance_ast_p90",
    "tirs": "standard_sh_p90",
    "tirs_cadres": "standard_sot_p90",
    "centres": "performance_crs_p90",
    "fautes_subies": "performance_fld_p90",
    "fautes_commises": "performance_fls_p90",
    "interceptions": "performance_int_p90",
    "tacles_gagnes": "performance_tklw_p90",
    "hors_jeu": "performance_off_p90",
}
U = {  # Understat, 5 grands championnats uniquement
    "xg_hors_pen": "us_np_xg_p90",
    "xa": "us_xa_p90",
    "passes_cles": "us_key_passes_p90",
    "xg_chain": "us_xg_chain_p90",
    "xg_buildup": "us_xg_buildup_p90",
}
TOUTES = {**M, **U}

METRIQUES = {
    "Ailier": {
        "all": ["fautes_subies", "centres", "passes_dec", "buts_hors_pen", "tirs",
                "hors_jeu", "tacles_gagnes"],
        "big5": ["xa", "passes_cles", "xg_hors_pen", "xg_chain"],
    },
    "Attaquant": {
        "all": ["buts_hors_pen", "tirs", "tirs_cadres", "hors_jeu", "passes_dec",
                "fautes_subies"],
        "big5": ["xg_hors_pen", "xa", "passes_cles", "xg_chain"],
    },
    "Milieu offensif": {
        "all": ["passes_dec", "tirs", "buts_hors_pen", "fautes_subies", "centres",
                "tacles_gagnes"],
        "big5": ["xa", "passes_cles", "xg_chain", "xg_buildup", "xg_hors_pen"],
    },
    "Milieu": {
        "all": ["tacles_gagnes", "interceptions", "fautes_commises", "passes_dec",
                "tirs", "fautes_subies"],
        "big5": ["xg_buildup", "xg_chain", "passes_cles", "xa"],
    },
    "Latéral": {
        "all": ["centres", "passes_dec", "tacles_gagnes", "interceptions",
                "fautes_subies", "fautes_commises"],
        "big5": ["xa", "passes_cles", "xg_buildup"],
    },
    "Défenseur central": {
        "all": ["tacles_gagnes", "interceptions", "fautes_commises", "buts_hors_pen",
                "fautes_subies"],
        "big5": ["xg_buildup", "xg_chain"],
    },
}

# 3. Archétypes : score = moyenne des percentiles listés ----------------------
#    (les métriques Understat ne comptent qu'en mode big5)
ARCHETYPES = {
    "Ailier": {
        "Dribbleur / percuteur": ["fautes_subies"],
        "Ailier centreur": ["centres", "passes_dec"],
        "Ailier finisseur": ["buts_hors_pen", "tirs", "xg_hors_pen"],
        "Ailier créateur": ["passes_dec", "xa", "passes_cles"],
    },
    "Attaquant": {
        "Renard des surfaces": ["buts_hors_pen", "tirs_cadres", "xg_hors_pen"],
        "Attaquant de profondeur": ["hors_jeu", "buts_hors_pen"],
        "Attaquant créateur / pivot": ["passes_dec", "fautes_subies", "xa", "passes_cles"],
    },
    "Milieu offensif": {
        "Meneur de jeu": ["passes_dec", "xa", "passes_cles"],
        "Milieu buteur": ["buts_hors_pen", "tirs", "xg_hors_pen"],
        "Percuteur": ["fautes_subies"],
    },
    "Milieu": {
        "Casseur / récupérateur": ["tacles_gagnes", "interceptions", "fautes_commises"],
        "Box-to-box": ["tacles_gagnes", "tirs", "fautes_subies"],
        "Organisateur": ["passes_dec", "xg_buildup", "passes_cles"],
    },
    "Latéral": {
        "Latéral offensif": ["centres", "passes_dec", "xa"],
        "Latéral défensif": ["tacles_gagnes", "interceptions"],
    },
    "Défenseur central": {
        "Stoppeur / casseur": ["tacles_gagnes", "fautes_commises"],
        "Défenseur d'anticipation": ["interceptions"],
        "Défenseur relanceur": ["xg_buildup"],          # big5 uniquement
    },
}
SEUIL_ARCHETYPE = 0.75     # score minimum pour recevoir un archétype

LOW_MAX, MID_MAX, HIGH_MAX = 5_000_000, 25_000_000, 70_000_000


def tranche(v):
    """low < 5 M€ <= medium < 25 M€ <= high < 70 M€ <= superstar."""
    if pd.isna(v):
        return "inconnu"
    if v < LOW_MAX:
        return "low"
    if v < MID_MAX:
        return "medium"
    if v < HIGH_MAX:
        return "high"
    return "superstar"


def norm(s):
    return unidecode(str(s)).lower().strip()


def charger_base(chemin=DATA):
    df = pd.read_csv(chemin)
    df["player_clean"] = df["player"].map(norm)      # même normalisation que la recherche
    df["groupe"] = df["tm_sub_position"].map(SUB_VERS_GROUPE)
    df["groupe"] = df["groupe"].fillna(df["pos_main"].map(FBREF_VERS_GROUPE))
    df["big5"] = df["league"].isin(BIG5)
    df["budget_tier"] = df["tm_value_eur"].map(tranche)
    return df


def metriques(groupe, mode):
    noms = list(METRIQUES[groupe]["all"])
    if mode == "big5":
        noms += METRIQUES[groupe]["big5"]
    return noms


def percentiles(df, groupe, mode):
    """Tableau des percentiles (0-1) des joueurs d'un groupe, dans le bassin du mode."""
    pool = df[df["groupe"] == groupe]
    if mode == "big5":
        pool = pool[pool["big5"] & pool["us_xg_p90"].notna()]
    noms = metriques(groupe, mode)
    p = pool[[TOUTES[n] for n in noms]].rank(pct=True)
    p.columns = noms
    return p


def archetype(df, mode="all"):
    """Ajoute 'archetype' et 'archetype_score' à chaque joueur."""
    df = df.copy()
    df["archetype"], df["archetype_score"] = "Polyvalent", np.nan
    for groupe, types in ARCHETYPES.items():
        p = percentiles(df, groupe, mode)
        scores = {}
        for nom, crit in types.items():
            crit = [c for c in crit if c in p.columns]
            if crit:
                scores[nom] = p[crit].mean(axis=1)
        s = pd.DataFrame(scores)
        meilleur, score = s.idxmax(axis=1), s.max(axis=1)
        df.loc[s.index, "archetype_score"] = score
        df.loc[s.index[score >= SEUIL_ARCHETYPE], "archetype"] = meilleur[score >= SEUIL_ARCHETYPE]
    return df


def trouver(df, nom):
    m = df[df["player_clean"].str.contains(norm(nom), regex=False)]
    if m.empty:
        raise ValueError(f"Joueur introuvable : {nom}")
    return m.sort_values("playing_time_min", ascending=False).index[0]


def embedding_pca(df, groupe, mode, variance=0.9):
    """Coordonnées ACP des joueurs d'un groupe : stats par 90 minutes centrées-réduites
    (valeurs extrêmes écrêtées à ±3 écarts-types), puis ACP gardant 90 % de la variance."""
    from sklearn.decomposition import PCA
    pool = df[df["groupe"] == groupe]
    if mode == "big5":
        pool = pool[pool["big5"] & pool["us_xg_p90"].notna()]
    X = pool[[TOUTES[n] for n in metriques(groupe, mode)]]
    X = X.fillna(X.median())
    Z = ((X - X.mean()) / X.std(ddof=0).replace(0, 1)).clip(-3, 3)
    P = PCA(n_components=variance, svd_solver="full").fit_transform(Z)
    return pd.DataFrame(P, index=pool.index)


def similaires_idx(df, i, mode="all", groupe=None, methode="percentiles"):
    """Tous les joueurs du même groupe, triés par similarité avec la ligne `i`.
    methode : "percentiles" (distance entre percentiles, par défaut) ou "pca"
    (ACP puis plus proches voisins). Renvoie (tableau trié, percentiles de la référence)."""
    groupe = groupe or df.at[i, "groupe"]
    p = percentiles(df, groupe, mode)
    if methode == "pca":
        E = embedding_pca(df, groupe, mode)
        if i not in E.index:
            raise ValueError(f"Ce joueur n'est pas dans le bassin '{mode}' du groupe {groupe}")
        dist = np.sqrt(((E - E.loc[i]) ** 2).sum(axis=1))
        res = df.loc[E.index].copy()
        res["similarite"] = ((1 - dist / dist.max()) * 100).round(1)   # relatif au plus éloigné du poste
        ref = p.loc[i] if i in p.index else None
        return res.drop(index=i).sort_values("similarite", ascending=False), ref
    if i not in p.index:   # la référence n'est pas dans le bassin (ex. hors big5)
        raise ValueError(f"Ce joueur n'est pas dans le bassin '{mode}' du groupe {groupe}")
    ref = p.loc[i]
    dist = np.sqrt(((p - ref) ** 2).sum(axis=1))
    dmax = np.sqrt(len(p.columns))           # distance max possible
    res = df.loc[p.index].copy()
    res["similarite"] = ((1 - dist / dmax) * 100).round(1)
    res = res.drop(index=i).sort_values("similarite", ascending=False)
    return res, ref


def similaires(df, nom, mode="all", n=10, groupe=None, age_max=None,
               marocains=False, par_budget=3, methode="percentiles"):
    """Joueurs les plus proches de `nom`.
    Renvoie (top_n global, meilleurs par tranche de budget)."""
    i = trouver(df, nom)
    res, ref = similaires_idx(df, i, mode, groupe, methode)
    res = res[["player", "team", "league", "age", "tm_sub_position",
               "playing_time_min", "tm_value_eur", "budget_tier",
               "is_moroccan", "similarite"]]
    if age_max:
        res = res[res["age"] <= age_max]
    if marocains:
        res = res[res["is_moroccan"]]
    tranches = {t: res[res["budget_tier"] == t].head(par_budget)
                for t in ["low", "medium", "high", "superstar"]}
    return res.head(n), tranches, ref

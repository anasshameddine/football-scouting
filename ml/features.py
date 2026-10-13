"""
Variables du modèle de valeur marchande.

Une ligne = un joueur sur une saison. Cible = logarithme de la valeur Transfermarkt
au 30 juin de la saison (valeur_fin_saison_eur).

`construire(df)` renvoie (X, y, meta) ; la même fonction sert à l'entraînement et à l'API.
"""

import numpy as np
import pandas as pd

SEUIL_MINUTES = 450

# Statistiques par 90 minutes retenues (FBref : partout ; Understat : 5 grands championnats)
P90_FBREF = ["performance_gls_p90", "performance_ast_p90", "performance_g_minus_pk_p90",
             "standard_sh_p90", "standard_sot_p90", "performance_crs_p90",
             "performance_int_p90", "performance_tklw_p90", "performance_fld_p90",
             "performance_fls_p90", "performance_off_p90", "performance_crdy_p90"]
P90_UNDERSTAT = ["us_np_xg_p90", "us_xa_p90", "us_key_passes_p90", "us_xg_chain_p90",
                 "us_xg_buildup_p90"]
POSTES = ["Centre-Back", "Left-Back", "Right-Back", "Defensive Midfield", "Central Midfield",
          "Attacking Midfield", "Left Midfield", "Right Midfield", "Left Winger",
          "Right Winger", "Second Striker", "Centre-Forward"]
POSTE_FBREF = {"DF": "Centre-Back", "MF": "Central Midfield", "FW": "Centre-Forward"}
LIGUES = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A", "GER-Bundesliga", "FRA-Ligue 1",
          "NED-Eredivisie", "POR-Primeira Liga", "BEL-Pro League", "TUR-Super Lig",
          "SCO-Premiership", "AUT-Bundesliga", "SUI-Super League", "DEN-Superliga",
          "KSA-Pro League"]
BIG5 = LIGUES[:5]


def filtrer(df):
    """Lignes utilisables : hors gardiens, assez de minutes."""
    return df[(df["pos_main"] != "GK") & (df["tm_sub_position"] != "Goalkeeper")
              & (df["playing_time_min"] >= SEUIL_MINUTES)].copy()


def contexte_equipe(df, cible="log_valeur"):
    """Valeur moyenne (log) des coéquipiers, sans le joueur lui-même : niveau du club.
    Calculée avec toutes les lignes valorisées du club et de la saison."""
    g = df.groupby(["club_key", "season"])[cible]
    somme, n = g.transform("sum"), g.transform("count")
    propre = df[cible].fillna(0)
    autres = n - df[cible].notna().astype(int)
    moy = (somme - propre) / autres.replace(0, np.nan)
    return moy.where(autres >= 4)


def construire(df, avec_contexte=True):
    """df : lignes de ml_base (déjà filtrées). Renvoie X, y (log valeur), meta."""
    df = df.copy()
    df["log_valeur"] = np.log(df["valeur_fin_saison_eur"].where(df["valeur_fin_saison_eur"] > 0))
    X = pd.DataFrame(index=df.index)
    X["age"] = df["age"]
    X["minutes"] = df["playing_time_min"]
    X["part_titulaire"] = df["playing_time_starts"] / df["playing_time_mp"].replace(0, np.nan)
    X["minutes_par_match"] = df["playing_time_min"] / df["playing_time_mp"].replace(0, np.nan)
    X["taille_cm"] = df["tm_height_cm"]
    X["pied_gauche"] = (df["tm_foot"] == "left").astype(float).where(df["tm_foot"].notna())
    X["big5"] = df["league"].isin(BIG5).astype(int)
    poste = df["tm_sub_position"].fillna(df["pos_main"].map(POSTE_FBREF))
    for p in POSTES:
        X[f"poste_{p}"] = (poste == p).astype(int)
    for lg in LIGUES:
        X[f"ligue_{lg}"] = (df["league"] == lg).astype(int)
    for c in P90_FBREF + P90_UNDERSTAT:
        X[c] = df[c]
    if avec_contexte:
        X["equipe_log_valeur_autres"] = contexte_equipe(df)
    meta = df[["player_key", "player", "team", "league", "season", "saison_label", "age",
               "playing_time_min", "is_moroccan", "valeur_fin_saison_eur", "tm_sub_position",
               "tm_player_id"]].copy()
    return X, df["log_valeur"], meta

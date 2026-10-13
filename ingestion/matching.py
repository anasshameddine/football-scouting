"""
Rapprochement des identifiants entre sources (étape qui reste en Python : dbt ne sait
pas faire de correspondance approximative sur des noms).

    python ingestion/matching.py

Lit raw.* dans PostgreSQL, écrit dans le schéma `mapping` :
    mapping.team_understat      clubs FBref <-> Understat, par ligue et saison
    mapping.player_understat    joueurs FBref <-> Understat, par ligue, saison et club
    mapping.player_transfermarkt  joueurs FBref <-> Transfermarkt, par nom d'origine et année de naissance

Chaque ligne indique la méthode (exact / proche) pour qu'on puisse auditer les rapprochements.
Les règles sont celles qui avaient été validées sur la saison 2025-2026 :
  1. correspondance exacte (nom normalisé) ;
  2. sinon tous les mots d'un nom sont inclus dans l'autre ;
  3. sinon même dernier mot ;
  4. sinon noms très proches (difflib).
Gardes-fous : minutes proches pour Understat ; même année de naissance et même
championnat pour Transfermarkt.
"""

import difflib
import re

import pandas as pd
from sqlalchemy import create_engine, text
from unidecode import unidecode

from common import journaliser, pg_url

CLUBS_UNDERSTAT = {   # noms Understat -> noms FBref (cas que la similarité ne trouve pas)
    "Leeds": "Leeds United", "Manchester United": "Manchester Utd",
    "Newcastle United": "Newcastle", "Nottingham Forest": "Nottingham",
    "Wolverhampton Wanderers": "Wolves", "Alaves": "Alavés",
    "Atletico Madrid": "Atlético Madrid", "Real Oviedo": "Oviedo",
    "Paris Saint Germain": "Paris SG", "Bayer Leverkusen": "Leverkusen",
    "Borussia Dortmund": "Dortmund", "Borussia M.Gladbach": "Gladbach",
    "Eintracht Frankfurt": "Frankfurt", "FC Cologne": "Köln",
    "FC Heidenheim": "Heidenheim", "RasenBallsport Leipzig": "RB Leipzig",
    "St. Pauli": "St Pauli", "VfB Stuttgart": "Stuttgart", "AC Milan": "Milan",
    "Parma Calcio 1913": "Parma", "Verona": "Hellas Verona",
}
LIGUE_VERS_TM = {"ENG-Premier League": "GB1", "ESP-La Liga": "ES1", "ITA-Serie A": "IT1",
                 "GER-Bundesliga": "L1", "FRA-Ligue 1": "FR1", "NED-Eredivisie": "NL1",
                 "POR-Primeira Liga": "PO1", "BEL-Pro League": "BE1",
                 "TUR-Super Lig": "TR1", "SCO-Premiership": "SC1",
                 "AUT-Bundesliga": "A1", "SUI-Super League": "C1",
                 "DEN-Superliga": "DK1", "KSA-Pro League": "SA1"}


def norm(s):
    return unidecode(str(s)).lower().strip()


def mots(nom):
    return set(re.split(r"[\s\-']+", nom))


def choisir(nom, candidats, cutoff):
    """Règles 2 à 4 : renvoie le nom choisi parmi `candidats` ou None."""
    mr = mots(nom)
    r1 = [n for n in candidats if mots(n) <= mr or mr <= mots(n)]
    if len(r1) == 1:
        return r1[0]
    r2 = [n for n in candidats if n.split()[-1] == nom.split()[-1]]
    if len(r2) == 1:
        return r2[0]
    r3 = difflib.get_close_matches(nom, candidats, n=1, cutoff=cutoff)
    return r3[0] if r3 else None


def minutes_num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")


# ----------------------------------------------------------------------------- Understat
def clubs_understat(fb, us):
    """Table (league, season, team_us, team_fbref) : nom exact, dictionnaire, puis similarité."""
    lignes = []
    for (lg, sa), g_us in us.groupby(["league", "season"]):
        teams_fb = sorted(fb[(fb["league"] == lg) & (fb["season"] == sa)]["team"].unique())
        for t in sorted(g_us["team"].unique()):
            t2 = CLUBS_UNDERSTAT.get(t, t)
            if t2 in teams_fb:
                lignes.append((lg, sa, t, t2, "exact" if t2 == t else "dictionnaire"))
                continue
            proche = difflib.get_close_matches(t, teams_fb, n=1, cutoff=0.6)
            if not proche:
                proche = [x for x in teams_fb if x in t or t in x][:1]
            lignes.append((lg, sa, t, proche[0] if proche else None,
                           "proche" if proche else "aucun"))
    return pd.DataFrame(lignes, columns=["league", "season", "team_us", "team", "methode"])


def joueurs_understat(fb, us, cm):
    us = us.merge(cm[["league", "season", "team_us", "team"]], left_on=["league", "season", "team"],
                  right_on=["league", "season", "team_us"], how="left", suffixes=("_us_orig", ""))
    us = us.dropna(subset=["team"])
    us["pc"] = us["player"].map(norm)
    fb = fb.copy()
    fb["pc"] = fb["player"].map(norm)
    cle = ["league", "season", "team", "pc"]
    us = us.drop_duplicates(cle)
    fb = fb.drop_duplicates(cle)
    exact = fb.merge(us, on=cle, how="inner", suffixes=("", "_us"))
    res = [(r.league, r.season, r.team, r.player, r.player_us, "exact")
           for r in exact.itertuples()]
    utilises = set(zip(exact["league"], exact["season"], exact["team"], exact["pc"]))
    reste = fb[[tuple(x) not in utilises for x in fb[cle].values]]
    us_idx = {k: g for k, g in us.groupby(["league", "season", "team"])}
    for r in reste.itertuples():
        g = us_idx.get((r.league, r.season, r.team))
        if g is None:
            continue
        g = g[[(r.league, r.season, r.team, p) not in utilises for p in g["pc"]]]
        tol = max(0.25 * (r.minutes if pd.notna(r.minutes) else 0), 90)
        g = g[(g["minutes_us"] - (r.minutes if pd.notna(r.minutes) else 0)).abs() <= tol]
        if g.empty:
            continue
        choix = choisir(r.pc, g["pc"].tolist(), 0.8)
        if choix:
            lig = g[g["pc"] == choix].iloc[0]
            utilises.add((r.league, r.season, r.team, choix))
            res.append((r.league, r.season, r.team, r.player, lig["player"], "proche"))
    return pd.DataFrame(res, columns=["league", "season", "team", "player", "player_us", "methode"])


# ----------------------------------------------------------------------------- Transfermarkt
def joueurs_tm(fb, tm):
    tm = tm.copy()
    tm["pc"] = tm["name"].map(norm)
    tm["born"] = pd.to_datetime(tm["date_of_birth"], errors="coerce").dt.year
    tm = tm.dropna(subset=["born"]).sort_values("market_value_in_eur", ascending=False,
                                                 na_position="last")
    tm["born"] = tm["born"].astype(float)
    fb = fb.copy()
    fb["pc"] = fb["player"].map(norm)
    fb["born"] = pd.to_numeric(fb["born"], errors="coerce")
    # un joueur FBref = (nom normalisé, année de naissance) ; ses championnats = tous ceux où il a joué
    joueurs = (fb.dropna(subset=["born"]).groupby(["pc", "born"])
                 .agg(player=("player", "first"),
                      ligues=("league", lambda s: sorted(set(s)))).reset_index())
    # Plusieurs joueurs Transfermarkt peuvent porter le même nom et la même année de naissance :
    # on garde celui qui joue dans le championnat du joueur FBref, puis le plus récemment actif,
    # puis le mieux valorisé.
    cand_ex = joueurs.merge(
        tm[["pc", "born", "player_id", "name", "last_season", "market_value_in_eur",
            "current_club_domestic_competition_id"]], on=["pc", "born"])
    cand_ex["comp_ok"] = [
        c in {LIGUE_VERS_TM[l] for l in ls if l in LIGUE_VERS_TM}
        for c, ls in zip(cand_ex["current_club_domestic_competition_id"], cand_ex["ligues"])]
    # Homonymes : si Transfermarkt connaît 2 joueurs de même nom et même année de naissance et que
    # FBref a des lignes dans 2 championnats, ce sont (probablement) 2 personnes, pas un transfert.
    # On rattache alors chaque championnat à son joueur Transfermarkt (colonne `league`).
    split, cles_split = [], set()
    for (pc, born), g in cand_ex.groupby(["pc", "born"]):
        ligs = g["ligues"].iloc[0]
        if len(g) < 2 or len(ligs) < 2:
            continue
        choisis = {}
        for lg in ligs:
            c = g[g["current_club_domestic_competition_id"] == LIGUE_VERS_TM.get(lg)]
            c = c.sort_values(["last_season", "market_value_in_eur"], ascending=False,
                              na_position="last")
            if not c.empty:
                choisis[lg] = c.iloc[0]
        if len({r["player_id"] for r in choisis.values()}) >= 2:
            cles_split.add((pc, born))
            split += [(pc, born, g["pc"].iloc[0], r["player_id"], r["name"], "exact", lg)
                      for lg, r in choisis.items()]
    cand_ok = cand_ex[[(a, b) not in cles_split for a, b in zip(cand_ex["pc"], cand_ex["born"])]]
    exact = (cand_ok.sort_values(["comp_ok", "last_season", "market_value_in_eur"],
                                 ascending=False, na_position="last")
             .drop_duplicates(["pc", "born"]))
    res = [(r.pc, r.born, r.player, r.player_id, r.name, "exact", None) for r in exact.itertuples()]
    res += split
    deja = set(exact["player_id"]) | {x[3] for x in split}
    traites = set(zip(exact["pc"], exact["born"])) | cles_split
    reste = joueurs[[(a, b) not in traites for a, b in zip(joueurs["pc"], joueurs["born"])]]
    par_annee = {y: g for y, g in tm.groupby("born")}
    for r in reste.itertuples():
        cand = par_annee.get(r.born)
        if cand is None:
            continue
        comps = {LIGUE_VERS_TM[l] for l in r.ligues if l in LIGUE_VERS_TM}
        if not comps:
            continue
        cand = cand[~cand["player_id"].isin(deja)]
        cand = cand[cand["current_club_domestic_competition_id"].isin(comps)]
        cand = cand.sort_values(["last_season", "market_value_in_eur"], ascending=False,
                                na_position="last").drop_duplicates("pc")
        if cand.empty:
            continue
        choix = choisir(r.pc, cand["pc"].tolist(), 0.85)
        if choix:
            lig = cand[cand["pc"] == choix].iloc[0]
            deja.add(lig["player_id"])
            res.append((r.pc, r.born, r.player, lig["player_id"], lig["name"], "proche", None))
    corr = pd.DataFrame(res, columns=["pc", "born", "_", "tm_player_id", "tm_name", "methode", "league"])
    # une ligne par graphie FBref (nom d'origine + année de naissance), clé de jointure dans dbt
    orig = fb.dropna(subset=["born"])[["player", "pc", "born"]].drop_duplicates()
    out = orig.merge(corr.drop(columns="_"), on=["pc", "born"])
    return out.drop(columns="pc")


def main():
    engine = create_engine(pg_url())
    fb = pd.read_sql(
        'select s.league, s.season, s.team, s.player, s.born, t.playing_time_min as minutes_txt '
        'from raw.fbref_standard s left join raw.fbref_playing_time t '
        'using (league, season, team, player)', engine)
    fb["minutes"] = minutes_num(fb["minutes_txt"])
    fb["season"] = fb["season"].astype(str)
    fb = fb.drop_duplicates(["league", "season", "team", "player"])
    us = pd.read_sql("select league, season, team, player, minutes as minutes_us "
                     "from raw.understat_player_season", engine)
    us["season"] = us["season"].astype(str)
    tm = pd.read_sql("select player_id, name, date_of_birth, market_value_in_eur, last_season, "
                     "current_club_domestic_competition_id from raw.tm_players "
                     "where last_season >= 2020", engine)

    cm = clubs_understat(fb, us)
    pu = joueurs_understat(fb, us, cm)
    pt = joueurs_tm(fb, tm)

    with engine.begin() as cx:
        cx.execute(text("create schema if not exists mapping"))
    for nom, df in [("team_understat", cm), ("player_understat", pu),
                    ("player_transfermarkt", pt)]:
        with engine.begin() as cx:
            cx.execute(text(f"drop table if exists mapping.{nom} cascade"))
        df.to_sql(nom, engine, schema="mapping", if_exists="replace", index=False)
        journaliser("matching", f"mapping.{nom}", f"mapping.{nom}", len(df))
        print(df["methode"].value_counts().to_dict())
    print("Clubs Understat sans correspondance :",
          cm[cm["methode"] == "aucun"][["league", "season", "team_us"]].values.tolist())


if __name__ == "__main__":
    main()

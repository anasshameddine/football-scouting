"""
Étape 4 — Dashboard de scouting (Streamlit)

Lancer depuis la racine du projet :
    streamlit run app\\app.py
"""

import html
import sys
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki import chercher as wiki_chercher  # noqa: E402
import assistant_ui  # noqa: E402
from profiles import (ARCHETYPES, HIGH_MAX, LOW_MAX, METRIQUES, MID_MAX, TOUTES,
                      archetype, charger_base, metriques, norm, percentiles,
                      similaires_idx)

st.set_page_config(page_title="Scouting football", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Sans+3:wght@400;600&display=swap');
html, body, .stApp, [data-testid="stSidebar"] {font-family:'Source Sans 3', sans-serif;}
h1, h2, h3, .nom, .titre, .tier-title, .val {font-family:'Barlow Condensed', sans-serif !important;
       letter-spacing:.2px;}
h2, h3 {font-weight:600 !important;}
.block-container {padding-top:2.2rem; max-width:1250px;}
.sub {color:#667068; font-size:.84rem; line-height:1.4;}
.row {display:flex; justify-content:space-between; gap:10px; padding:10px 0 9px 0;
      border-bottom:1px solid #d7dbd3;}
.row .nom {font-weight:600; font-size:1.22rem; line-height:1.15;}
.row .val {font-weight:600; font-size:1.2rem; white-space:nowrap; text-align:right;}
.row .sim {font-size:.8rem; color:#667068; text-align:right; white-space:nowrap;}
.nom a {color:inherit; text-decoration:none; border-bottom:1px solid transparent;}
.nom a:hover {border-bottom-color:#1f4d3a;}
.retour a {color:#667068; text-decoration:none; font-size:.9rem;}
.bio {font-size:1rem; line-height:1.5; margin:6px 0 4px 0;}
.mar {color:#b3262d; font-weight:600; font-size:.8rem; margin-left:6px;}
.trait {height:3px; margin-top:6px; background:#dfe2da;}
.trait div {height:100%;}
.tier-title {font-weight:700; font-size:1.6rem; line-height:1.1;
             padding-bottom:4px; margin-bottom:2px;}
.tier-sub {color:#667068; font-size:.84rem; margin-bottom:4px;}
.hero {padding:4px 0 14px 0; margin-bottom:10px; border-bottom:2px solid #1c2420;}
.hero .titre {font-size:3.4rem; font-weight:700; line-height:1.0;}
.hero .ligne {font-size:1.05rem; margin-top:6px;}
.resume {font-size:1.02rem; margin:2px 0 6px 0;}
.estime {border-left:3px solid #1f4d3a; padding:2px 0 2px 12px; margin:10px 0 6px 0;
         font-size:1.02rem;}
.proche {border-left:3px solid #b3262d; padding:2px 0 2px 12px; margin:10px 0 22px 0;
         font-size:1.02rem;}
</style>
""", unsafe_allow_html=True)

LANG = "fr"


def t(fr, en):
    """Texte dans la langue choisie."""
    return fr if LANG == "fr" else en


LABELS_FR = {
    "buts_hors_pen": "Buts hors pen.", "passes_dec": "Passes déc.", "tirs": "Tirs",
    "tirs_cadres": "Tirs cadrés", "centres": "Centres",
    "fautes_subies": "Fautes subies", "fautes_commises": "Fautes commises",
    "interceptions": "Interceptions", "tacles_gagnes": "Tacles gagnés",
    "hors_jeu": "Hors-jeu", "xg_hors_pen": "xG hors pen.", "xa": "xA",
    "passes_cles": "Passes clés", "xg_chain": "xG Chain", "xg_buildup": "xG Buildup",
}
LABELS_EN = {
    "buts_hors_pen": "Non-pen. goals", "passes_dec": "Assists", "tirs": "Shots",
    "tirs_cadres": "Shots on target", "centres": "Crosses",
    "fautes_subies": "Fouls drawn", "fautes_commises": "Fouls committed",
    "interceptions": "Interceptions", "tacles_gagnes": "Tackles won",
    "hors_jeu": "Offsides", "xg_hors_pen": "Non-pen. xG", "xa": "xA",
    "passes_cles": "Key passes", "xg_chain": "xG Chain", "xg_buildup": "xG Buildup",
}
GROUPE_EN = {"Ailier": "Winger", "Attaquant": "Forward", "Milieu offensif": "Attacking midfielder",
             "Milieu": "Midfielder", "Latéral": "Full-back", "Défenseur central": "Centre-back"}
ARCH_EN = {
    "Dribbleur / percuteur": "Dribbler / ball carrier", "Ailier centreur": "Crossing winger",
    "Ailier finisseur": "Goal-scoring winger", "Ailier créateur": "Creative winger",
    "Renard des surfaces": "Poacher", "Attaquant de profondeur": "Runner in behind",
    "Attaquant créateur / pivot": "Creative forward / target man", "Meneur de jeu": "Playmaker",
    "Milieu buteur": "Goal-scoring midfielder", "Percuteur": "Ball carrier",
    "Casseur / récupérateur": "Ball winner", "Box-to-box": "Box-to-box",
    "Organisateur": "Deep-lying organiser", "Latéral offensif": "Attacking full-back",
    "Latéral défensif": "Defensive full-back", "Stoppeur / casseur": "Stopper",
    "Défenseur d'anticipation": "Reading-the-game defender", "Défenseur relanceur": "Ball-playing defender",
    "Polyvalent": "All-rounder",
}
POSTE_FR = {"Centre-Back": "Défenseur central", "Left-Back": "Latéral gauche",
            "Right-Back": "Latéral droit", "Defensive Midfield": "Milieu défensif",
            "Central Midfield": "Milieu central", "Attacking Midfield": "Milieu offensif",
            "Left Midfield": "Milieu gauche", "Right Midfield": "Milieu droit",
            "Left Winger": "Ailier gauche", "Right Winger": "Ailier droit",
            "Second Striker": "Second attaquant", "Centre-Forward": "Avant-centre"}


def lab(n):
    return (LABELS_FR if LANG == "fr" else LABELS_EN)[n]


def grp(g):
    return g if LANG == "fr" else GROUPE_EN.get(g, g)


def arch(a):
    return a if LANG == "fr" else ARCH_EN.get(a, a)


def poste(p):
    if pd.isna(p):
        return "n.d." if LANG == "fr" else "n/a"
    return POSTE_FR.get(p, p) if LANG == "fr" else p


M_ = lambda v: f"{v / 1e6:.0f}"
TIER_ORDRE = [("low", "#3f7d5a"), ("medium", "#3a6ea5"), ("high", "#b9772b"),
              ("superstar", "#6b4a8f")]
TIER_COULEUR = {k: c for k, c in TIER_ORDRE}
TIER_COULEUR["inconnu"] = "#888888"


def tiers():
    """(clé, titre, fourchette, couleur) dans la langue courante."""
    return [
        ("low", "Low cost", t(f"moins de {M_(LOW_MAX)} M€", f"under €{M_(LOW_MAX)}M"), "#3f7d5a"),
        ("medium", t("Moyen", "Mid-range"), t(f"{M_(LOW_MAX)} à {M_(MID_MAX)} M€",
                                              f"€{M_(LOW_MAX)}M to €{M_(MID_MAX)}M"), "#3a6ea5"),
        ("high", "High cost", t(f"{M_(MID_MAX)} à {M_(HIGH_MAX)} M€",
                                f"€{M_(MID_MAX)}M to €{M_(HIGH_MAX)}M"), "#b9772b"),
        ("superstar", "Superstar", t(f"plus de {M_(HIGH_MAX)} M€", f"over €{M_(HIGH_MAX)}M"), "#6b4a8f"),
    ]


def tier_titre(k):
    return {c: ti for c, ti, _, _ in tiers()}.get(k, t("Inconnu", "Unknown"))


SEUIL_PRUDENCE = 50e6   # au-delà, le modèle sous-estime en moyenne (voir docs/modele_valeur_resultats.md)
EXEMPLES = ["Doku", "Lamine Yamal", "Hakimi", "Saibari", "Ezzalzouli", "Bouaddi"]


def style(fig, h=520):
    fig.update_layout(height=h, margin=dict(t=20, b=20), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Source Sans 3, sans-serif", color="#1c2420"))
    return fig


def fmt_val(v):
    if pd.isna(v):
        return t("n.d.", "n/a")
    if LANG == "fr":
        return f"{v / 1e6:.0f} M€" if v >= 100e6 else f"{v / 1e6:.1f} M€".replace(".", ",")
    return f"€{v / 1e6:.0f}M" if v >= 100e6 else f"€{v / 1e6:.1f}M"


def entier(v):
    return int(v) if pd.notna(v) else t("n.d.", "n/a")


@st.cache_data(show_spinner="Calcul des profils...")
def preparer(mode):
    df = archetype(charger_base(), mode)
    sg = pd.Series(np.nan, index=df.index)
    for g in METRIQUES:
        p = percentiles(df, g, mode)
        sg.loc[p.index] = p.mean(axis=1)
    df["score_global"] = sg
    return df[df["score_global"].notna()]


RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "data" / "processed"


@st.cache_data
def charger_valeurs():
    """Valeur réelle et prédite par joueur et par saison (produit par ml/train_value.py)."""
    f = DOSSIER / "valeur_predite.csv"
    return pd.read_csv(f, dtype={"season": str}) if f.exists() else None


@st.cache_data
def charger_sous_cotes():
    f = DOSSIER / "joueurs_sous_cotes.csv"
    return pd.read_csv(f, dtype={"season": str}) if f.exists() else None


def etiquette(df, i):
    r = df.loc[i]
    return f"{r.player} — {r.team} ({r.league}, {fmt_val(r.tm_value_eur)})"


def choisir(nom):
    st.session_state["recherche"] = nom


def lien_url(tid):
    """Adresse de la fiche d'un joueur (garde la langue et la recherche en cours)."""
    q = quote(str(st.session_state.get("recherche", "") or ""))
    return f"?joueur={int(tid)}&lang={LANG}&q={q}"


def nom_cliquable(nom, tid):
    n = html.escape(str(nom))
    return f'<a href="{lien_url(tid)}" target="_self">{n}</a>' if pd.notna(tid) else n


def colonne_fiche(tab, ids):
    """Ajoute à un tableau une colonne « Fiche » avec un lien vers la fiche du joueur."""
    tab = tab.copy()
    tab[t("Fiche", "Profile")] = [lien_url(i) if pd.notna(i) else None for i in ids]
    cfg = {t("Fiche", "Profile"): st.column_config.LinkColumn(
        t("Fiche", "Profile"), display_text=t("Ouvrir", "Open"))}
    return tab, cfg


def carte(r, couleur):
    mar = '<span class="mar">MAR</span>' if r.is_moroccan else ""
    sim = max(0.0, min(float(r.similarite), 100.0))
    return (f'<div class="row"><div><div class="nom">{nom_cliquable(r.player, r.tm_player_id)}{mar}</div>'
            f'<div class="sub">{html.escape(r.team)}, {html.escape(r.league)}</div>'
            f'<div class="sub">{entier(r.age)} {t("ans", "y/o")}, '
            f'{html.escape(arch(str(r.archetype)))}</div></div>'
            f'<div><div class="val">{fmt_val(r.tm_value_eur)}</div>'
            f'<div class="sim">{t(f"{sim:.0f} % proche", f"{sim:.0f}% similar")}</div>'
            f'<div class="trait"><div style="width:{sim}%;background:{couleur}"></div></div>'
            f'</div></div>')


COLS_HIST = ["tm_player_id", "player", "born", "season", "saison_label", "team", "league", "age",
             "playing_time_min", "playing_time_mp", "playing_time_starts", "performance_gls",
             "performance_ast", "performance_g_minus_pk", "standard_sh", "performance_tklw",
             "performance_int", "us_xg", "us_xa", "us_key_passes", "performance_gls_p90",
             "performance_ast_p90", "performance_g_minus_pk_p90", "standard_sh_p90",
             "performance_tklw_p90", "performance_int_p90", "us_xg_p90", "us_xa_p90",
             "us_key_passes_p90", "valeur_fin_saison_eur", "tm_sub_position", "nation_code"]


@st.cache_data(show_spinner=False)
def charger_historique():
    """Une ligne par joueur et saison (ml_base), pour les statistiques des dernières saisons."""
    f = DOSSIER / "ml_base.csv.gz"
    if not f.exists():
        return None
    return pd.read_csv(f, usecols=lambda c: c in COLS_HIST, dtype={"season": str}, low_memory=False)


@st.cache_data(ttl=30 * 24 * 3600, show_spinner=False)
def biographie(nom, born, club, lang):
    """Résumé Wikipédia dans la langue choisie, sinon dans l'autre langue."""
    for lg in (lang, "en" if lang == "fr" else "fr"):
        r = wiki_chercher(nom, born, lg, club=club)
        if r:
            return {**r, "langue": lg}
    return None


def donnees_fiche(tid):
    """Rassemble tout ce qu'il faut pour la fiche d'un joueur (None si inconnu)."""
    hist_all = charger_historique()
    h = (hist_all[hist_all["tm_player_id"] == tid].sort_values("season")
         if hist_all is not None else pd.DataFrame())
    if h.empty:
        return None
    der = h.iloc[-1]
    base = preparer("all")
    cur = base[base["tm_player_id"] == tid]
    valeurs = charger_valeurs()
    pred = (valeurs[valeurs["tm_player_id"] == tid].sort_values("season")
            if valeurs is not None else pd.DataFrame())
    born = der["born"] if pd.notna(der["born"]) else None
    return {"h": h, "der": der, "nom": der["player"], "born": der["born"], "club": der["team"],
            "base": base, "cur": cur, "ref": cur.iloc[0] if not cur.empty else None, "pred": pred,
            "bio": biographie(der["player"], born, der["team"], LANG)}


def entete_fiche(d):
    """Photo, nom, valeur, estimation du modèle et biographie."""
    der, nom, born, ref, pred, bio = d["der"], d["nom"], d["born"], d["ref"], d["pred"], d["bio"]
    avec_photo = bool(bio and bio.get("image"))
    c_photo, c_txt = st.columns([1, 4]) if avec_photo else (None, st.container())
    if avec_photo:
        c_photo.image(bio["image"], width=170)
        c_photo.caption(t("Photo : Wikimedia / Wikipédia", "Photo: Wikimedia / Wikipedia"))
    with c_txt:
        grp_txt = grp(ref.groupe) if ref is not None else poste(der["tm_sub_position"])
        pied = {"left": t("gauche", "left"), "right": t("droit", "right"), "both": t("les deux", "both")}
        details = [grp_txt,
                   arch(str(ref.archetype)) if ref is not None else None,
                   f"{entier(der['age'])} {t('ans', 'years old')}",
                   str(der["nation_code"]) if pd.notna(der["nation_code"]) else None,
                   t(f"né en {int(born)}", f"born {int(born)}") if pd.notna(born) else None]
        if ref is not None:
            if pd.notna(ref.tm_foot):
                details.append(t(f"pied {pied.get(ref.tm_foot, ref.tm_foot)}",
                                 f"{pied.get(ref.tm_foot, ref.tm_foot)} footed"))
            if pd.notna(ref.tm_height_cm):
                details.append(f"{entier(ref.tm_height_cm)} cm")
        valeur_txt = ""
        if ref is not None:
            valeur_txt = (f'. {t("Valeur :", "Value:")} <b>{fmt_val(ref.tm_value_eur)}</b> '
                          f'(<span style="color:{TIER_COULEUR[ref.budget_tier]};font-weight:600">'
                          f'{tier_titre(ref.budget_tier).lower()}</span>)')
        st.markdown(
            f'<div class="hero"><div class="titre">{html.escape(str(nom))}</div>'
            f'<div class="ligne">{html.escape(str(der["team"]))}, {html.escape(str(der["league"]))}'
            f'{valeur_txt}</div><div class="sub">{html.escape(", ".join(d for d in details if d))}</div></div>',
            unsafe_allow_html=True)
        if not pred.empty:
            p = pred.iloc[-1]
            st.markdown(
                '<div class="estime">' + t(
                    f"Estimation du modèle ({html.escape(str(p.saison_label))}) : <b>{fmt_val(p.valeur_predite_eur)}</b> "
                    f"(fourchette à 80 % : {fmt_val(p.valeur_predite_basse_eur)} à {fmt_val(p.valeur_predite_haute_eur)}), "
                    f"contre {fmt_val(p.valeur_reelle_eur)} sur Transfermarkt.",
                    f"Model estimate ({html.escape(str(p.saison_label))}): <b>{fmt_val(p.valeur_predite_eur)}</b> "
                    f"(80% range: {fmt_val(p.valeur_predite_basse_eur)} to {fmt_val(p.valeur_predite_haute_eur)}), "
                    f"versus {fmt_val(p.valeur_reelle_eur)} on Transfermarkt.") + '</div>',
                unsafe_allow_html=True)
            avert = note_prudence(p.valeur_predite_eur)
            if avert:
                st.markdown(f'<div class="sub" style="margin:0 0 6px 15px"><i>{avert}</i></div>',
                            unsafe_allow_html=True)
    if bio:
        extrait = html.escape(bio["extrait"])
        lien = (f' <a href="{bio["url"]}" target="_blank">{t("Lire sur Wikipédia", "Read on Wikipedia")}</a>'
                if bio.get("url") else "")
        note = (t(" (article en anglais)", " (French article)") if bio["langue"] != LANG else "")
        st.markdown(f'<div class="bio">{extrait}{note}{lien}</div>', unsafe_allow_html=True)
    else:
        st.caption(t("Biographie indisponible (pas de page Wikipédia trouvée, ou pas de connexion).",
                     "Biography unavailable (no Wikipedia page found, or no connection)."))



def onglet_stats(h):
    """Statistiques de chaque saison : totaux puis par 90 minutes."""
    ordre = h.sort_values("season", ascending=False)
    tot = ordre[["saison_label", "team", "league", "age", "playing_time_min", "playing_time_mp",
                 "performance_gls", "performance_ast", "us_xg", "us_xa",
                 "standard_sh", "us_key_passes", "performance_tklw", "performance_int"]].copy()
    tot.columns = [t("Saison", "Season"), t("Club", "Club"), t("Championnat", "League"),
                   t("Âge", "Age"), t("Minutes", "Minutes"), t("Matchs", "Matches"),
                   t("Buts", "Goals"), t("Passes déc.", "Assists"),
                   "xG", "xA", t("Tirs", "Shots"), t("Passes clés", "Key passes"),
                   t("Tacles gagnés", "Tackles won"), t("Interceptions", "Interceptions")]
    st.dataframe(tot.round(1), hide_index=True, width="stretch")
    st.markdown(f"**{t('Par 90 minutes', 'Per 90 minutes')}**")
    p90 = ordre[["saison_label", "performance_gls_p90", "performance_ast_p90",
                 "performance_g_minus_pk_p90", "standard_sh_p90", "us_xg_p90", "us_xa_p90",
                 "us_key_passes_p90", "performance_tklw_p90", "performance_int_p90"]].copy()
    p90.columns = [t("Saison", "Season"), t("Buts", "Goals"), t("Passes déc.", "Assists"),
                   t("Buts hors pen.", "Non-pen. goals"), t("Tirs", "Shots"), "xG", "xA",
                   t("Passes clés", "Key passes"), t("Tacles gagnés", "Tackles won"),
                   t("Interceptions", "Interceptions")]
    st.dataframe(p90.round(2), hide_index=True, width="stretch")
    st.caption(t("xG, xA et passes clés (Understat) n'existent que pour les 5 grands championnats. "
                 "Les saisons jouées hors des 14 championnats suivis n'apparaissent pas.",
                 "xG, xA and key passes (Understat) exist only for the top 5 leagues. "
                 "Seasons played outside the 14 tracked leagues are not shown."))


def _vers_recherche():
    """Depuis une fiche : lance une nouvelle recherche (retire le joueur de l'adresse)."""
    st.session_state["recherche"] = st.session_state.get("autre_recherche", "")
    if "joueur" in st.query_params:
        del st.query_params["joueur"]


def barre_fiche(d):
    """Menu de gauche d'une fiche : recherche, résumé de la saison, proches, navigation."""
    sb = st.sidebar
    sb.text_input(t("Rechercher un autre joueur", "Search another player"), key="autre_recherche",
                  placeholder=t("Ex. : Doku, Yamal, Saibari...", "E.g. Doku, Yamal, Saibari..."),
                  on_change=_vers_recherche)
    der, ref, pred = d["der"], d["ref"], d["pred"]
    sb.markdown(f"**{t('Saison', 'Season')} {html.escape(str(der['saison_label']))}**")
    lignes = [t(f"{entier(der['playing_time_min'])} minutes, {entier(der['playing_time_mp'])} matchs",
                f"{entier(der['playing_time_min'])} minutes, {entier(der['playing_time_mp'])} matches"),
              t(f"{entier(der['performance_gls'])} buts, {entier(der['performance_ast'])} passes décisives",
                f"{entier(der['performance_gls'])} goals, {entier(der['performance_ast'])} assists")]
    if pd.notna(der["us_xg"]):
        lignes.append(f"xG {der['us_xg']:.1f}, xA {der['us_xa']:.1f}")
    if not pred.empty:
        p = pred.iloc[-1]
        lignes.append(t(f"Valeur {fmt_val(p.valeur_reelle_eur)}, estimée {fmt_val(p.valeur_predite_eur)}",
                        f"Value {fmt_val(p.valeur_reelle_eur)}, estimated {fmt_val(p.valeur_predite_eur)}"))
    sb.markdown("".join(f'<div class="sub">{html.escape(x)}</div>' for x in lignes),
                unsafe_allow_html=True)
    if ref is not None:
        res, _ = similaires_idx(d["base"], d["cur"].index[0], "all")
        sb.markdown(f"**{t('Joueurs les plus proches', 'Closest players')}**")
        sb.markdown("".join(
            f'<div class="row"><div class="nom" style="font-size:1.05rem">{nom_cliquable(r.player, r.tm_player_id)}'
            f'<div class="sub">{html.escape(r.team)}</div></div>'
            f'<div class="sim">{r.similarite:.0f}%</div></div>'
            for r in res.head(5).itertuples()), unsafe_allow_html=True)
    q = quote(str(st.session_state.get("recherche", "") or ""))
    sb.markdown(
        f'<div class="retour" style="margin-top:14px"><a href="?lang={LANG}&q={q}" target="_self">'
        f'{t("← Recherche de joueurs", "← Player search")}</a><br>'
        f'<a href="?lang={LANG}&page=sous_cotes" target="_self">'
        f'{t("→ Joueurs sous-cotés", "→ Undervalued players")}</a><br>'
        f'<a href="?lang={LANG}&page=assistant" target="_self">'
        f'{t("→ Assistant IA", "→ AI assistant")}</a></div>', unsafe_allow_html=True)


def faits_rapport(d):
    """Faits calculés par le projet, donnés au modèle qui rédige le rapport de scouting."""
    der, ref, pred, h = d["der"], d["ref"], d["pred"], d["h"]
    m = lambda v: round(float(v) / 1e6, 1) if pd.notna(v) else None  # noqa: E731
    f = {"joueur": str(d["nom"]), "age": entier(der["age"]), "club": der["team"],
         "championnat": der["league"], "poste": poste(der["tm_sub_position"]),
         "nationalite": der["nation_code"] if pd.notna(der["nation_code"]) else None}
    if ref is not None:
        f.update(pied=ref.tm_foot if pd.notna(ref.tm_foot) else None,
                 taille_cm=int(ref.tm_height_cm) if pd.notna(ref.tm_height_cm) else None,
                 selections=int(ref.tm_intl_caps) if pd.notna(ref.tm_intl_caps) else None,
                 fin_contrat=str(ref.tm_contract_end)[:10] if pd.notna(ref.tm_contract_end) else None,
                 archetype=arch(str(ref.archetype)), score_global=round(float(ref.score_global) * 100),
                 valeur_actuelle_meur=m(ref.tm_value_eur), valeur_max_meur=m(ref.tm_peak_value_eur))
        noms = metriques(ref.groupe, "all")
        pct = percentiles(d["base"], ref.groupe, "all").loc[d["cur"].index[0]]
        items = sorted(((lab(n), round(float(ref[TOUTES[n]]), 2), round(float(pct[n]) * 100)) for n in noms),
                       key=lambda x: -x[2])
        k = min(4, len(items) // 2)          # forces et faiblesses sans recouvrement
        f["points_forts"], f["points_faibles"] = items[:k], items[k:][-3:][::-1]
        res, _ = similaires_idx(d["base"], d["cur"].index[0], "all")
        f["similaires"] = [(r.player, r.team, round(float(r.similarite)), m(r.tm_value_eur))
                           for r in res.head(5).itertuples()]
    if not pred.empty:
        p = pred.iloc[-1]
        f["estimation_modele_meur"] = m(p.valeur_predite_eur)
        f["fourchette_meur"] = f"{m(p.valeur_predite_basse_eur)} - {m(p.valeur_predite_haute_eur)}"
        f["prudence"] = bool(p.valeur_predite_eur >= SEUIL_PRUDENCE)
        f.setdefault("valeur_actuelle_meur", m(p.valeur_reelle_eur))
    f["saisons"] = [{"saison": s.saison_label, "club": s.team, "minutes": entier(s.playing_time_min),
                     "matchs": entier(s.playing_time_mp), "buts": entier(s.performance_gls),
                     "passes": entier(s.performance_ast),
                     "xg": round(float(s.us_xg), 1) if pd.notna(s.us_xg) else None,
                     "xa": round(float(s.us_xa), 1) if pd.notna(s.us_xa) else None}
                    for s in h.sort_values("season").tail(4).itertuples()]
    if d["bio"]:
        f["biographie"] = d["bio"]["extrait"][:1200]
    return f


def chercher_joueurs(requete):
    """[(tm_player_id, libellé), ...] des joueurs dont le nom contient la requête (dernière saison connue)."""
    hist = charger_historique()
    if hist is None:
        return []
    der = hist.dropna(subset=["tm_player_id"]).sort_values("season").drop_duplicates("tm_player_id", keep="last")
    der = der[der["player"].map(norm).str.contains(norm(requete), regex=False)]
    der = der.sort_values("valeur_fin_saison_eur", ascending=False).head(20)
    return [(float(r.tm_player_id), f"{r.player} — {r.team} ({r.saison_label})") for r in der.itertuples()]


def faits_pour(tid):
    d = donnees_fiche(tid)
    return faits_rapport(d) if d else None


def fiche_joueur(tid):
    """Page complète d'un joueur : bio, photo, valeur, prédiction, statistiques par saison."""
    q = quote(str(st.session_state.get("recherche", "") or ""))
    st.markdown(f'<div class="retour"><a href="?lang={LANG}&q={q}" target="_self">'
                f'{t("← Retour à la recherche", "← Back to search")}</a></div>', unsafe_allow_html=True)
    d = donnees_fiche(tid)
    if d is None:
        st.warning(t("Joueur introuvable dans la base.", "Player not found in the database."))
        return
    h, base, cur, ref, pred, nom = d["h"], d["base"], d["cur"], d["ref"], d["pred"], d["nom"]
    barre_fiche(d)
    entete_fiche(d)

    tab_stats, tab_valeur, tab_profil, tab_sim, tab_rapport = st.tabs(
        [t("Statistiques par saison", "Season stats"), t("Évolution de la valeur", "Value over time"),
         t("Profil", "Profile"), t("Joueurs similaires", "Similar players"),
         t("Rapport de scouting (IA)", "Scouting report (AI)")])

    with tab_rapport:
        assistant_ui.bloc_rapport(t, LANG, faits_rapport(d), f"fiche_{int(tid)}")

    with tab_stats:
        onglet_stats(h)

    with tab_valeur:
        if pred.empty:
            st.info(t("Pas de prédiction pour ce joueur (moins de 450 minutes ou gardien).",
                      "No prediction for this player (under 450 minutes, or goalkeeper)."))
        else:
            fig = go.Figure()
            x = pred["saison_label"]
            fig.add_trace(go.Scatter(x=x, y=pred["valeur_predite_haute_eur"] / 1e6, mode="lines",
                                     line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=x, y=pred["valeur_predite_basse_eur"] / 1e6, mode="lines",
                                     line=dict(width=0), fill="tonexty", fillcolor="rgba(31,77,58,0.15)",
                                     name=t("Fourchette prédite (80 %)", "Predicted range (80%)"),
                                     hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=x, y=pred["valeur_predite_eur"] / 1e6, mode="lines+markers",
                                     name=t("Valeur prédite", "Predicted value"),
                                     line=dict(color="#1f4d3a", dash="dash"), marker=dict(size=8)))
            fig.add_trace(go.Scatter(x=x, y=pred["valeur_reelle_eur"] / 1e6, mode="lines+markers",
                                     name=t("Valeur Transfermarkt", "Transfermarkt value"),
                                     line=dict(color="#1c2420", width=3), marker=dict(size=9)))
            fig.update_yaxes(title=t("Valeur (M€)", "Value (€M)"), gridcolor="#e3e6df", rangemode="tozero")
            fig.update_xaxes(gridcolor="#e3e6df", type="category")
            fig.update_layout(legend=dict(orientation="h", y=-0.15))
            style(fig, 420)
            st.plotly_chart(fig, width="stretch")
            st.caption(t("Valeurs au 30 juin de chaque saison. Chaque prédiction vient d'un modèle "
                         "qui n'a pas vu la saison correspondante.",
                         "Values on 30 June of each season. Each prediction comes from a model "
                         "that has not seen the corresponding season."))

    with tab_profil:
        if ref is None:
            st.info(t("Profil détaillé disponible seulement pour les joueurs de la saison 2025-2026 "
                      "(au moins 450 minutes, hors gardiens).",
                      "Detailed profile only available for 2025-26 players "
                      "(at least 450 minutes, goalkeepers excluded)."))
        else:
            noms = metriques(ref.groupe, "all")
            pct = percentiles(base, ref.groupe, "all").loc[cur.index[0]]
            etiq = [lab(n) for n in noms]
            vals = [float(pct[n]) * 100 for n in noms]
            fig = go.Figure(go.Scatterpolar(r=vals + vals[:1], theta=etiq + etiq[:1], fill="toself",
                                            opacity=0.4, line_color="#1f4d3a", name=str(nom)))
            fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], gridcolor="#d7dbd3"),
                                         angularaxis=dict(gridcolor="#d7dbd3"), bgcolor="rgba(0,0,0,0)"),
                              showlegend=False)
            style(fig, 420)
            g1, g2 = st.columns([3, 2])
            g1.plotly_chart(fig, width="stretch")
            g2.markdown(f"**{t('Archétype', 'Archetype')}** : {arch(str(ref.archetype))}  \n"
                        f"**{t('Score global', 'Overall score')}** : {ref.score_global * 100:.0f} / 100")
            g2.dataframe(pd.DataFrame({t("Métrique (par 90 min)", "Metric (per 90 min)"): etiq,
                                       t("Valeur", "Value"): [round(float(ref[TOUTES[n]]), 2) for n in noms],
                                       "Percentile": [round(v) for v in vals]}),
                         hide_index=True, width="stretch")
            g2.caption(t("Percentile dans son poste, parmi les 14 championnats (100 = meilleur).",
                         "Percentile within his position across the 14 leagues (100 = best)."))

    with tab_sim:
        if ref is None:
            st.info(t("Joueurs similaires disponibles seulement pour la saison 2025-2026.",
                      "Similar players only available for the 2025-26 season."))
        else:
            res, _ = similaires_idx(base, cur.index[0], "all")
            for col, (cle, titre, fourchette, couleur) in zip(st.columns(4), tiers()):
                with col:
                    st.markdown(f'<div class="tier-title" style="border-bottom:3px solid {couleur}">{titre}</div>'
                                f'<div class="tier-sub">{fourchette}</div>', unsafe_allow_html=True)
                    for _, r in res[res["budget_tier"] == cle].head(3).iterrows():
                        st.markdown(carte(r, couleur), unsafe_allow_html=True)


# --------------------------------------------------------------- langue
_qp = st.query_params
if "langue" not in st.session_state:
    st.session_state["langue"] = "English" if _qp.get("lang") == "en" else "Français"
if _qp.get("page") in ("sous_cotes", "assistant") and "page" not in st.session_state:
    st.session_state["page"] = _qp.get("page")
if "recherche" not in st.session_state and _qp.get("q"):
    st.session_state["recherche"] = _qp.get("q")
choix_langue = st.sidebar.radio("Langue / Language", ["Français", "English"], horizontal=True,
                                key="langue")
LANG = "fr" if choix_langue == "Français" else "en"
TIERS = tiers()
MODES = {t("Large : 14 championnats (stats FBref)", "Wide: 14 leagues (FBref stats)"): "all",
         t("Complet : 5 grands championnats (avec xG, xA, passes clés)",
           "Full: top 5 leagues (with xG, xA, key passes)"): "big5"}


def note_prudence(valeur):
    """Avertissement si la valeur prédite est dans la zone où le modèle sous-estime."""
    if pd.notna(valeur) and valeur >= SEUIL_PRUDENCE:
        return t("Estimation supérieure à 50 M€ : le modèle sous-estime en moyenne de 30 % les "
                 "joueurs au-dessus de 70 M€. À lire comme une estimation prudente.",
                 "Estimate above €50M: on average the model underestimates players above €70M "
                 "by 30%. Read it as a conservative estimate.")
    return ""


# --------------------------------------------------------------- fiche d'un joueur
_joueur = st.query_params.get("joueur")
if _joueur and str(_joueur).isdigit():
    st.sidebar.title(t("Scouting football", "Football scouting"))
    fiche_joueur(float(_joueur))
    st.stop()

# --------------------------------------------------------------- barre latérale
st.sidebar.title(t("Scouting football", "Football scouting"))
PAGES = {"recherche": t("Recherche de joueurs", "Player search"),
         "sous_cotes": t("Joueurs sous-cotés", "Undervalued players"),
         "assistant": t("Assistant IA", "AI assistant")}
if charger_sous_cotes() is None:
    del PAGES["sous_cotes"]
if st.session_state.get("page") not in PAGES:
    st.session_state["page"] = "recherche"
page = st.sidebar.radio(t("Page", "Page"), list(PAGES), format_func=PAGES.get, key="page")

if page == "assistant":
    assistant_ui.page_assistant(t, LANG, chercher_joueurs, faits_pour)
    st.stop()

if page == "sous_cotes":
    sc = charger_sous_cotes()
    st.markdown(
        f'<div class="hero"><div class="titre">{t("Joueurs sous-cotés", "Undervalued players")}</div>'
        f'<div class="ligne">' + t(
            "Joueurs dont la valeur Transfermarkt est inférieure à ce que prédit le modèle "
            "d'après leurs statistiques, leur poste, leur âge et le niveau de leur club.",
            "Players whose Transfermarkt value is below what the model predicts from their "
            "stats, position, age and club level.") + '</div></div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    lg_sc = f1.multiselect(t("Championnats", "Leagues"), sorted(sc["league"].unique()),
                           default=[], placeholder=t("Tous", "All"))
    postes_sc = f2.multiselect(t("Postes", "Positions"),
                               sorted(sc["tm_sub_position"].dropna().unique()), default=[],
                               placeholder=t("Tous", "All"), format_func=poste)
    age_sc = f3.slider(t("Âge maximum", "Maximum age"), 16, 28, 28)
    val_sc = f4.slider(t("Valeur réelle maximum (M€)", "Maximum actual value (€M)"),
                       0.5, 60.0, 60.0, step=0.5)
    ma_sc = st.checkbox(t("Joueurs marocains uniquement", "Moroccan players only"))
    d = sc[sc["age"].le(age_sc) & sc["valeur_reelle_eur"].le(val_sc * 1e6)]
    if lg_sc:
        d = d[d["league"].isin(lg_sc)]
    if postes_sc:
        d = d[d["tm_sub_position"].isin(postes_sc)]
    if ma_sc:
        d = d[d["is_moroccan"].astype(bool)]
    d = d.sort_values("ecart_eur", ascending=False)
    saison_sc = sc["saison_label"].iloc[0]
    st.markdown('<div class="resume">' + t(
        f"{len(d)} joueurs de la saison {saison_sc}. Classés par écart en euros entre la valeur "
        "prédite et la valeur Transfermarkt.",
        f"{len(d)} players, {saison_sc} season. Ranked by the gap in euros between the "
        "predicted value and the Transfermarkt value.") + '</div>', unsafe_allow_html=True)
    if d.empty:
        st.info(t("Aucun joueur avec ces filtres.", "No player matches these filters."))
        st.stop()
    gauche, droite = st.columns(2)
    for col, part in zip((gauche, droite), (d.head(10), d.iloc[10:20])):
        for _, r in part.iterrows():
            mar = '<span class="mar">MAR</span>' if r.is_moroccan else ""
            larg = max(0.0, min(float(r.ecart_pct), 300.0)) / 3
            prud = (f'<div class="sub"><i>{t("estimation haute, prudence", "high estimate, be cautious")}'
                    f'</i></div>' if r.valeur_predite_eur >= SEUIL_PRUDENCE else "")
            col.markdown(
                f'<div class="row"><div><div class="nom">{nom_cliquable(r.player, r.tm_player_id)}{mar}</div>'
                f'<div class="sub">{html.escape(r.team)}, {html.escape(r.league)}</div>'
                f'<div class="sub">{entier(r.age)} {t("ans", "y/o")}, '
                f'{html.escape(poste(r.tm_sub_position))}</div>{prud}</div>'
                f'<div><div class="val">{fmt_val(r.valeur_reelle_eur)}</div>'
                f'<div class="sim">{t("estimé", "estimated")} {fmt_val(r.valeur_predite_eur)}, '
                f'{t(f"+{r.ecart_pct:.0f} %", f"+{r.ecart_pct:.0f}%")}</div>'
                f'<div class="trait"><div style="width:{larg}%;background:#1f4d3a"></div></div>'
                f'</div></div>', unsafe_allow_html=True)
    top15 = d.head(15).iloc[::-1]
    fig = go.Figure()
    for _, r in top15.iterrows():
        fig.add_trace(go.Scatter(x=[r.valeur_reelle_eur / 1e6, r.valeur_predite_eur / 1e6],
                                 y=[r.player, r.player], mode="lines", showlegend=False,
                                 line=dict(color="#b8beb3", width=3), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=top15["valeur_reelle_eur"] / 1e6, y=top15["player"],
                             mode="markers", name=t("Valeur Transfermarkt", "Transfermarkt value"),
                             marker=dict(color="#667068", size=10)))
    fig.add_trace(go.Scatter(x=top15["valeur_predite_eur"] / 1e6, y=top15["player"],
                             mode="markers", name=t("Valeur prédite", "Predicted value"),
                             marker=dict(color="#1f4d3a", size=10)))
    fig.update_xaxes(type="log", gridcolor="#e3e6df",
                     title=t("Valeur (M€, échelle logarithmique)", "Value (€M, log scale)"))
    fig.update_yaxes(gridcolor="#e3e6df")
    fig.update_layout(legend=dict(orientation="h", y=-0.18))
    style(fig, 560)
    st.plotly_chart(fig, width="stretch")
    st.caption(t(
        "Lecture : plus le trait est long, plus le modèle voit de marge. Critères : valeur réelle "
        "sous la fourchette basse prédite (80 %), au moins 50 % d'écart, 900 minutes, 28 ans "
        "maximum, 500 k€ minimum. Le modèle sous-estime les très hautes valeurs (environ 30 % "
        "au-dessus de 70 M€) : les écarts les plus fiables concernent les budgets bas et moyens. "
        "C'est une piste à vérifier, pas une certitude.",
        "How to read: the longer the line, the more room the model sees. Criteria: actual value "
        "below the low end of the predicted range (80%), at least 50% gap, 900 minutes, "
        "28 years old at most, €500k minimum. The model underestimates very high values (about "
        "30% above €70M): the most reliable gaps are in low and mid budgets. It is a lead to "
        "check, not a certainty."))
    tab = d[["player", "team", "league", "age", "tm_sub_position", "valeur_reelle_eur",
             "valeur_predite_basse_eur", "valeur_predite_eur", "ecart_pct", "playing_time_min",
             "is_moroccan"]].copy()
    tab["tm_sub_position"] = tab["tm_sub_position"].map(poste)
    for c in ("valeur_reelle_eur", "valeur_predite_basse_eur", "valeur_predite_eur"):
        tab[c] = tab[c].map(fmt_val)
    tab["ecart_pct"] = tab["ecart_pct"].round(0).astype(int)
    tab.columns = [t("Joueur", "Player"), t("Club", "Club"), t("Championnat", "League"),
                   t("Âge", "Age"), t("Poste", "Position"), t("Valeur réelle", "Actual value"),
                   t("Prédite (bas)", "Predicted (low)"), t("Prédite", "Predicted"),
                   t("Écart %", "Gap %"), t("Minutes", "Minutes"), t("Marocain", "Moroccan")]
    tab_l, cfg = colonne_fiche(tab, d["tm_player_id"])
    st.dataframe(tab_l, hide_index=True, width="stretch", column_config=cfg)
    st.download_button(t("Télécharger (CSV)", "Download (CSV)"),
                       tab.to_csv(index=False).encode("utf-8"),
                       file_name="joueurs_sous_cotes.csv", mime="text/csv")
    st.stop()

mode = MODES[st.sidebar.radio(t("Base de comparaison", "Comparison pool"), list(MODES))]
METHODES = {t("Percentiles par poste", "Percentiles by position"): "percentiles",
            t("ACP + plus proches voisins", "PCA + nearest neighbours"): "pca"}
methode = METHODES[st.sidebar.radio(t("Méthode de similarité", "Similarity method"), list(METHODES),
                                    help=t("Les percentiles donnent un score lisible de 0 à 100. "
                                           "L'ACP compare des profils statistiques réduits à "
                                           "l'essentiel. Comparaison : docs/similarite_comparaison.md",
                                           "Percentiles give a readable 0-100 score. PCA compares "
                                           "statistical profiles reduced to the essentials. "
                                           "Comparison: docs/similarite_comparaison.md"))]
df = preparer(mode)
df_all = preparer("all")

st.sidebar.text_input(t("Rechercher un joueur", "Search for a player"), key="recherche",
                      placeholder=t("Ex. : Doku, Yamal, Saibari...", "E.g. Doku, Yamal, Saibari..."))
requete = norm(st.session_state.get("recherche", ""))
trouves = pd.DataFrame()
i_ref = None
if requete:
    trouves = df_all[df_all["player_clean"].str.contains(requete, regex=False)]
    trouves = trouves.sort_values("tm_value_eur", ascending=False, na_position="last").head(40)
    if trouves.empty:
        st.sidebar.warning(t("Aucun joueur trouvé. Essaie une partie du nom.",
                             "No player found. Try part of the name."))
    else:
        i_ref = st.sidebar.selectbox(t("Joueur", "Player"), list(trouves.index),
                                     format_func=lambda i: etiquette(df_all, i))

age_min, age_max = st.sidebar.slider(t("Âge des candidats", "Candidates' age"), 15, 42, (15, 42))
toutes_ligues = sorted(df["league"].unique())
with st.sidebar.expander(t("Championnats", "Leagues")):
    ligues = st.multiselect(t("Choix des championnats", "Choose leagues"), toutes_ligues,
                            default=toutes_ligues, label_visibility="collapsed")
seulement_ma = st.sidebar.checkbox(t("Joueurs marocains uniquement", "Moroccan players only"))
par_tranche = st.sidebar.slider(t("Joueurs par tranche de budget", "Players per budget tier"), 3, 10, 3)
st.sidebar.caption(t("Saison 2025-2026. Sources : FBref, Understat, Transfermarkt "
                     "(valeurs jusqu'en juillet 2026).",
                     "2025-26 season. Sources: FBref, Understat, Transfermarkt "
                     "(values up to July 2026)."))

# --------------------------------------------------------------- page d'accueil
if i_ref is None:
    st.markdown(
        f'<div class="hero"><div class="titre">'
        f'{t("Trouver le joueur qui lui ressemble", "Find the player who plays like him")}</div>'
        f'<div class="ligne">' + t(
            "Choisis un joueur de référence : on cherche les profils les plus proches, classés par "
            "budget. Tape un nom à gauche ou pars d'un exemple.",
            "Pick a reference player: we look for the closest profiles, ranked by budget. "
            "Type a name on the left or start from an example.") + '</div></div>',
        unsafe_allow_html=True)
    cols = st.columns(len(EXEMPLES))
    for col, nom in zip(cols, EXEMPLES):
        col.button(nom, key=f"ex_{nom}", on_click=choisir, args=(nom,), width="stretch")
    st.subheader(t("Les 10 joueurs marocains les plus chers de la base",
                   "The 10 most valuable Moroccan players in the database"))
    top_ma = df_all[df_all["is_moroccan"]].sort_values("tm_value_eur", ascending=False).head(10)
    aff = top_ma[["player", "team", "league", "age", "groupe", "tm_value_eur"]].copy()
    aff["groupe"] = aff["groupe"].map(grp)
    aff["tm_value_eur"] = aff["tm_value_eur"].map(fmt_val)
    aff.columns = [t("Joueur", "Player"), t("Club", "Club"), t("Championnat", "League"),
                   t("Âge", "Age"), t("Poste", "Position"), t("Valeur", "Value")]
    aff_l, cfg = colonne_fiche(aff, top_ma["tm_player_id"])
    st.dataframe(aff_l, hide_index=True, width="stretch", column_config=cfg)
    st.stop()

if i_ref not in df.index:
    st.title(t("Scouting football", "Football scouting"))
    st.warning(t(
        f"{df_all.at[i_ref, 'player']} n'est pas dans la base « Complet » (5 grands championnats "
        "avec données Understat). Passe en mode « Large » dans la barre de gauche.",
        f"{df_all.at[i_ref, 'player']} is not in the 'Full' pool (top 5 leagues with Understat "
        "data). Switch to 'Wide' in the sidebar."))
    st.stop()

ref = df.loc[i_ref]
res, p_ref = similaires_idx(df, i_ref, mode, methode=methode)
masque = res["age"].between(age_min, age_max) & res["league"].isin(ligues)
if seulement_ma:
    masque &= res["is_moroccan"]
res_f = res[masque]


# --------------------------------------------------------------- joueur de référence
_tid = ref.tm_player_id
_d = donnees_fiche(float(_tid)) if pd.notna(_tid) else None
hist = pd.DataFrame()
if _d is not None:       # fiche complète : photo, biographie, valeur, estimation du modèle
    entete_fiche(_d)
    hist = _d["pred"]
else:                    # joueur sans identifiant Transfermarkt : en-tête simple
    tier_ref = ref.budget_tier
    pied = {"left": t("gauche", "left"), "right": t("droit", "right"), "both": t("les deux", "both")}
    details = [grp(ref.groupe), arch(str(ref.archetype)), f"{entier(ref.age)} {t('ans', 'years old')}",
               t(f"pied {pied.get(ref.tm_foot, ref.tm_foot)}", f"{pied.get(ref.tm_foot, ref.tm_foot)} footed")
               if pd.notna(ref.tm_foot) else None,
               f"{entier(ref.tm_height_cm)} cm" if pd.notna(ref.tm_height_cm) else None,
               t(f"{int(ref.playing_time_min)} minutes jouées", f"{int(ref.playing_time_min)} minutes played")]
    st.markdown(
        f'<div class="hero"><div class="titre">{html.escape(ref.player)}</div>'
        f'<div class="ligne">{html.escape(ref.team)}, {html.escape(ref.league)}. '
        f'{t("Valeur :", "Value:")} <b>{fmt_val(ref.tm_value_eur)}</b> '
        f'(<span style="color:{TIER_COULEUR[tier_ref]};font-weight:600">'
        f'{tier_titre(tier_ref).lower()}</span>)</div>'
        f'<div class="sub">{html.escape(", ".join(d for d in details if d))}</div></div>',
        unsafe_allow_html=True)

    valeurs = charger_valeurs()
    hist = pd.DataFrame()
    if valeurs is not None and pd.notna(ref.tm_player_id):
        hist = valeurs[valeurs["tm_player_id"] == ref.tm_player_id].sort_values("season")
    if not hist.empty:
        h = hist.iloc[-1]
        st.markdown(
            '<div class="estime">' + t(
                f"Estimation du modèle ({html.escape(str(h.saison_label))}) : <b>{fmt_val(h.valeur_predite_eur)}</b> "
                f"(fourchette à 80 % : {fmt_val(h.valeur_predite_basse_eur)} à "
                f"{fmt_val(h.valeur_predite_haute_eur)}), contre {fmt_val(h.valeur_reelle_eur)} "
                "sur Transfermarkt.",
                f"Model estimate ({html.escape(str(h.saison_label))}): <b>{fmt_val(h.valeur_predite_eur)}</b> "
                f"(80% range: {fmt_val(h.valeur_predite_basse_eur)} to "
                f"{fmt_val(h.valeur_predite_haute_eur)}), versus {fmt_val(h.valeur_reelle_eur)} "
                "on Transfermarkt.") + '</div>', unsafe_allow_html=True)
        avert = note_prudence(h.valeur_predite_eur)
        if avert:
            st.markdown(f'<div class="sub" style="margin:0 0 6px 15px"><i>{avert}</i></div>',
                        unsafe_allow_html=True)

top10 = res_f.head(10)
moy = f"{top10['similarite'].mean():.0f} %" if len(top10) else t("n.d.", "n/a")
st.markdown('<div class="resume">' + t(
    f"{len(res_f)} candidats après filtres. Similarité moyenne du top 10 : <b>{moy}</b>. "
    f"{int(res_f.head(50)['is_moroccan'].sum())} Marocains dans le top 50.",
    f"{len(res_f)} candidates after filters. Average similarity of the top 10: <b>{moy}</b>. "
    f"{int(res_f.head(50)['is_moroccan'].sum())} Moroccans in the top 50.") + '</div>',
    unsafe_allow_html=True)

meilleur_ma = res[res["is_moroccan"]].head(1)
if not meilleur_ma.empty:
    m = meilleur_ma.iloc[0]
    st.markdown('<div class="proche">' + t(
        f"Le joueur marocain le plus proche est <b>{html.escape(m.player)}</b> "
        f"({html.escape(m.team)}, {html.escape(m.league)}), à {m.similarite:.0f} % pour "
        f"{fmt_val(m.tm_value_eur)}.",
        f"The closest Moroccan player is <b>{html.escape(m.player)}</b> "
        f"({html.escape(m.team)}, {html.escape(m.league)}), {m.similarite:.0f}% similar at "
        f"{fmt_val(m.tm_value_eur)}.") + '</div>', unsafe_allow_html=True)

# --------------------------------------------------------------- quatre budgets
st.subheader(t("Les plus proches, par budget", "Closest players, by budget"))
for col, (cle, titre, fourchette, couleur) in zip(st.columns(4), TIERS):
    with col:
        st.markdown(f'<div class="tier-title" style="border-bottom:3px solid {couleur}">{titre}</div>'
                    f'<div class="tier-sub">{fourchette}</div>', unsafe_allow_html=True)
        sous = res_f[res_f["budget_tier"] == cle].head(par_tranche)
        if sous.empty:
            st.caption(t("Aucun joueur avec ces filtres.", "No player matches these filters."))
        for _, r in sous.iterrows():
            st.markdown(carte(r, couleur), unsafe_allow_html=True)

# --------------------------------------------------------------- onglets
tab_radar, tab_stats, tab_val, tab_map, tab_table, tab_pepites = st.tabs(
    [t("Radar", "Radar"), t("Statistiques par saison", "Season stats"),
     t("Évolution de la valeur", "Value over time"),
     t("Valeur et similarité", "Value and similarity"), t("Tableau complet", "Full table"),
     t("Pépites", "Hidden gems")])

with tab_radar:
    top = res_f.head(30)
    if top.empty:
        st.info(t("Aucun candidat avec ces filtres.", "No candidate matches these filters."))
    else:
        i_cand = st.selectbox(t("Comparer avec", "Compare with"), list(top.index),
                              format_func=lambda i: f"{top.at[i, 'player']} "
                                                    f"({top.at[i, 'team']}, "
                                                    f"{top.at[i, 'similarite']:.0f} %)")
        cand = df.loc[i_cand]
        noms = metriques(ref.groupe, mode)
        p = percentiles(df, ref.groupe, mode)
        etiq = [lab(n) for n in noms]
        fig = go.Figure()
        for nom, ligne, couleur in [(ref.player, p.loc[i_ref], "#1f4d3a"),
                                    (cand.player, p.loc[i_cand], "#b3262d")]:
            vals = [float(ligne[n]) * 100 for n in noms]
            fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=etiq + etiq[:1],
                                          name=nom, fill="toself", opacity=0.35,
                                          line_color=couleur))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], gridcolor="#d7dbd3"),
                                     angularaxis=dict(gridcolor="#d7dbd3"), bgcolor="rgba(0,0,0,0)"),
                          legend=dict(orientation="h", y=-0.1))
        style(fig)
        g1, g2 = st.columns([3, 2])
        g1.plotly_chart(fig, width="stretch")
        detail = pd.DataFrame({
            t("Métrique (par 90 min)", "Metric (per 90 min)"): etiq,
            ref.player: [round(float(ref[TOUTES[n]]), 2) for n in noms],
            cand.player: [round(float(cand[TOUTES[n]]), 2) for n in noms],
        })
        g2.dataframe(detail, hide_index=True, width="stretch")
        g2.caption(t("Le radar montre le percentile du joueur dans son poste "
                     "(100 = meilleur de la base). Le tableau donne les valeurs brutes.",
                     "The radar shows the player's percentile within his position "
                     "(100 = best in the database). The table gives the raw values."))

with tab_stats:
    if _d is None:
        st.info(t("Pas d'historique pour ce joueur (identifiant Transfermarkt manquant).",
                  "No history for this player (missing Transfermarkt id)."))
    else:
        onglet_stats(_d["h"])

with tab_val:
    if hist.empty:
        st.info(t("Pas d'historique de valeur pour ce joueur (moins de 450 minutes sur la "
                  "période, gardien, ou identifiant Transfermarkt manquant).",
                  "No value history for this player (under 450 minutes over the period, "
                  "goalkeeper, or missing Transfermarkt id)."))
    else:
        fig = go.Figure()
        x = hist["saison_label"]
        fig.add_trace(go.Scatter(x=x, y=hist["valeur_predite_haute_eur"] / 1e6, mode="lines",
                                 line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x, y=hist["valeur_predite_basse_eur"] / 1e6, mode="lines",
                                 line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(31,77,58,0.15)",
                                 name=t("Fourchette prédite (80 %)", "Predicted range (80%)"),
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x, y=hist["valeur_predite_eur"] / 1e6, mode="lines+markers",
                                 name=t("Valeur prédite", "Predicted value"),
                                 line=dict(color="#1f4d3a", dash="dash"), marker=dict(size=8)))
        fig.add_trace(go.Scatter(x=x, y=hist["valeur_reelle_eur"] / 1e6, mode="lines+markers",
                                 name=t("Valeur Transfermarkt", "Transfermarkt value"),
                                 line=dict(color="#1c2420", width=3), marker=dict(size=9)))
        fig.update_yaxes(title=t("Valeur (M€)", "Value (€M)"), gridcolor="#e3e6df",
                         rangemode="tozero")
        fig.update_xaxes(gridcolor="#e3e6df", type="category")
        fig.update_layout(legend=dict(orientation="h", y=-0.15))
        style(fig, 420)
        st.plotly_chart(fig, width="stretch")
        tv = hist[["saison_label", "team", "age", "playing_time_min", "valeur_reelle_eur",
                   "valeur_predite_eur"]].copy()
        tv["valeur_reelle_eur"] = tv["valeur_reelle_eur"].map(fmt_val)
        tv["valeur_predite_eur"] = tv["valeur_predite_eur"].map(fmt_val)
        tv.columns = [t("Saison", "Season"), t("Club", "Club"), t("Âge", "Age"),
                      t("Minutes", "Minutes"), t("Valeur Transfermarkt", "Transfermarkt value"),
                      t("Valeur prédite", "Predicted value")]
        st.dataframe(tv, hide_index=True, width="stretch")
        st.caption(t("Valeurs au 30 juin de chaque saison. Chaque prédiction vient d'un modèle "
                     "qui n'a pas vu la saison correspondante.",
                     "Values on 30 June of each season. Each prediction comes from a model "
                     "that has not seen the corresponding season."))

with tab_map:
    nuage = res_f[res_f["tm_value_eur"].notna()].head(150).copy()
    if nuage.empty:
        st.info(t("Aucun candidat avec ces filtres.", "No candidate matches these filters."))
    else:
        cle_val = t("Valeur (M€)", "Value (€M)")
        cle_bud = t("Budget", "Budget")
        cle_sim = t("Similarité avec le joueur de référence (%)", "Similarity to the reference player (%)")
        nuage[cle_val] = nuage["tm_value_eur"] / 1e6
        nuage[cle_bud] = nuage["budget_tier"].map(tier_titre)
        fig = px.scatter(nuage, x="similarite", y=cle_val, color=cle_bud,
                         hover_name="player",
                         hover_data={"team": True, "league": True, "age": True,
                                     "similarite": ":.1f", cle_val: ":.1f", cle_bud: False},
                         log_y=True,
                         color_discrete_map={tier_titre(k): TIER_COULEUR[k]
                                             for k, _, _, _ in TIERS},
                         labels={"similarite": cle_sim})
        for seuil in (LOW_MAX, MID_MAX, HIGH_MAX):
            fig.add_hline(y=seuil / 1e6, line_dash="dot", opacity=0.5, line_color="#667068")
        fig.update_traces(marker=dict(size=9, opacity=0.85, line=dict(width=0)))
        fig.update_xaxes(gridcolor="#e3e6df"); fig.update_yaxes(gridcolor="#e3e6df")
        style(fig)
        st.plotly_chart(fig, width="stretch")
        st.caption(t("Les bonnes affaires sont en bas à droite : très proches du joueur "
                     "de référence, mais peu chers. Échelle logarithmique.",
                     "Bargains are at the bottom right: very close to the reference player "
                     "but cheap. Log scale."))

with tab_table:
    affiche = res_f.head(100)[["player", "team", "league", "age", "tm_sub_position",
                               "archetype", "tm_value_eur", "budget_tier", "similarite",
                               "playing_time_min", "is_moroccan"]].copy()
    affiche["tm_sub_position"] = affiche["tm_sub_position"].map(poste)
    affiche["archetype"] = affiche["archetype"].map(arch)
    affiche["tm_value_eur"] = affiche["tm_value_eur"].map(fmt_val)
    affiche["budget_tier"] = affiche["budget_tier"].map(tier_titre)
    affiche.columns = [t("Joueur", "Player"), t("Club", "Club"), t("Championnat", "League"),
                       t("Âge", "Age"), t("Poste", "Position"), t("Archétype", "Archetype"),
                       t("Valeur", "Value"), t("Budget", "Budget"),
                       t("Similarité %", "Similarity %"), t("Minutes", "Minutes"),
                       t("Marocain", "Moroccan")]
    aff_l, cfg = colonne_fiche(affiche, res_f.head(100)["tm_player_id"])
    st.dataframe(aff_l, hide_index=True, width="stretch", column_config=cfg)
    st.download_button(t("Télécharger (CSV)", "Download (CSV)"),
                       affiche.to_csv(index=False).encode("utf-8"),
                       file_name=f"proches_{ref.player.replace(' ', '_')}.csv",
                       mime="text/csv")

with tab_pepites:
    st.write(t("Les meilleurs profils d'un poste dans un budget donné, "
               "classés par score global (moyenne des percentiles du poste).",
               "The best profiles for a position within a given budget, "
               "ranked by overall score (average of the position's percentiles)."))
    groupes = list(METRIQUES)
    p1, p2, p3, p4 = st.columns(4)
    groupe = p1.selectbox(t("Poste", "Position"), groupes, index=groupes.index(ref.groupe),
                          format_func=grp)
    types = list(ARCHETYPES[groupe]) + ["Polyvalent"]
    choix = p2.multiselect(t("Archétype", "Archetype"), types, default=[], format_func=arch)
    age_pep = p3.slider(t("Âge maximum", "Maximum age"), 16, 40, 23)
    val_pep = p4.slider(t("Valeur maximum (M€)", "Maximum value (€M)"), 0.5, 100.0, 10.0, step=0.5)

    pep = df[(df["groupe"] == groupe) & df["age"].le(age_pep)
             & df["tm_value_eur"].le(val_pep * 1e6) & df["league"].isin(ligues)]
    if choix:
        pep = pep[pep["archetype"].isin(choix)]
    if seulement_ma:
        pep = pep[pep["is_moroccan"]]
    pep = pep.sort_values("score_global", ascending=False).head(30)
    if pep.empty:
        st.info(t("Aucun joueur avec ces critères.", "No player matches these criteria."))
    else:
        aff = pep[["player", "team", "league", "age", "archetype", "tm_value_eur",
                   "score_global", "playing_time_min", "is_moroccan"]].copy()
        aff["archetype"] = aff["archetype"].map(arch)
        aff["tm_value_eur"] = aff["tm_value_eur"].map(fmt_val)
        aff["score_global"] = (aff["score_global"] * 100).round(0)
        aff.columns = [t("Joueur", "Player"), t("Club", "Club"), t("Championnat", "League"),
                       t("Âge", "Age"), t("Archétype", "Archetype"), t("Valeur", "Value"),
                       t("Score /100", "Score /100"), t("Minutes", "Minutes"),
                       t("Marocain", "Moroccan")]
        aff_l, cfg = colonne_fiche(aff, pep["tm_player_id"])
        st.dataframe(aff_l, hide_index=True, width="stretch", column_config=cfg)

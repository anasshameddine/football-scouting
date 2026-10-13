"""
Page « Assistant » du dashboard et bloc « Rapport de scouting » de la fiche joueur.

L'assistant tourne en local avec Ollama et lit PostgreSQL : si l'un des deux n'est pas lancé,
la page l'explique au lieu de planter. Le reste du dashboard fonctionne sans eux.
"""

import html
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from assistant import llm, rag, report, sql_agent
    ERREUR_IMPORT = None
except Exception as e:  # dépendance manquante (sqlglot...) : la page le dira
    llm = rag = report = sql_agent = None
    ERREUR_IMPORT = f"{type(e).__name__}: {e}"

EXEMPLES_SQL = {
    "fr": ["Quels sont les 10 meilleurs buteurs marocains cette saison ?",
           "Top 10 des xA par 90 minutes en Premier League cette saison (au moins 900 minutes)",
           "Quels joueurs de moins de 21 ans valent plus de 20 M€ ?",
           "Quels sont les 10 joueurs les plus sous-cotés selon le modèle cette saison ?",
           "Comment a évolué la valeur de Brahim Díaz à la fin de chaque saison ?",
           "Quel est l'âge moyen des joueurs dans chaque championnat cette saison ?"],
    "en": ["Who are the 10 top Moroccan scorers this season?",
           "Top 10 xA per 90 minutes in the Premier League this season (at least 900 minutes)",
           "Which players under 21 are worth more than €20M?",
           "Who are the 10 most undervalued players according to the model this season?",
           "How did Brahim Díaz's value change at the end of each season?",
           "What is the average player age in each league this season?"],
}
EXEMPLES_RAG = {
    "fr": ["Dans quel centre de formation Bilal El Khannouss a-t-il été formé ?",
           "Quels trophées Achraf Hakimi a-t-il gagnés ?",
           "Quels joueurs ont été formés à La Masia ?",
           "Comment s'est passée la Coupe du monde 2022 pour Azzedine Ounahi ?"],
    "en": ["Which academy did Bilal El Khannouss come through?",
           "What trophies has Achraf Hakimi won?",
           "Which players came through La Masia?",
           "How did the 2022 World Cup go for Azzedine Ounahi?"],
}


def _etat(t):
    """État d'Ollama, revérifié au plus toutes les 20 secondes."""
    if ERREUR_IMPORT:
        return False, t(f"Module assistant indisponible ({ERREUR_IMPORT}). Lance : pip install -r requirements.txt",
                        f"Assistant module unavailable ({ERREUR_IMPORT}). Run: pip install -r requirements.txt")
    cache = st.session_state.get("_etat_ollama")
    if not cache or time.time() - cache[0] > 20:
        cache = (time.time(), *llm.etat())
        st.session_state["_etat_ollama"] = cache
    return cache[1], cache[2]


def _erreur(t, e):
    """Message clair pour les pannes attendues (Ollama arrêté, base arrêtée, index vide)."""
    nom = type(e).__name__
    if llm and isinstance(e, llm.OllamaIndisponible):
        st.error(str(e))
    elif nom in ("OperationalError",):
        st.error(t("PostgreSQL ne répond pas. Lance la base : docker compose up -d",
                   "PostgreSQL is not responding. Start it: docker compose up -d"))
    elif "bio_passages" in str(e) or "vector" in str(e):
        st.error(t("Index des biographies absent. Lance : python -m assistant.rag --limite 500",
                   "Biography index missing. Run: python -m assistant.rag --limite 500"))
    else:
        st.error(f"{nom} : {e}")


def _question(t, cle, exemples, aide):
    ex = st.selectbox(t("Exemples", "Examples"), exemples, index=None, key=f"ex_{cle}",
                      placeholder=t("Choisir un exemple ou écrire sa question", "Pick an example or type a question"))
    with st.form(f"form_{cle}"):
        q = st.text_area(t("Question", "Question"), value=ex or "", height=80, help=aide)
        envoyer = st.form_submit_button(t("Demander", "Ask"), type="primary")
    return q.strip() if envoyer else None


def onglet_sql(t, lang):
    q = _question(t, "sql", EXEMPLES_SQL[lang],
                  t("Question chiffrée sur la base : le modèle écrit une requête SQL, elle est vérifiée puis "
                    "exécutée en lecture seule.",
                    "Numbers question: the model writes a SQL query, which is checked then run read-only."))
    if q:
        with st.spinner(t("Le modèle écrit la requête...", "The model is writing the query...")):
            try:
                st.session_state["rep_sql"] = sql_agent.repondre(q, lang)
            except Exception as e:
                _erreur(t, e)
    rep = st.session_state.get("rep_sql")
    if not rep:
        return
    st.markdown(f"**{html.escape(rep.question)}**")
    if rep.erreur:
        st.error(t(f"Je n'ai pas trouvé de requête valide ({rep.erreur}). Essaie de reformuler.",
                   f"No valid query found ({rep.erreur}). Try rephrasing."))
    else:
        st.markdown(rep.texte)
        st.dataframe(rep.donnees, hide_index=True, width="stretch")
        if rep.tronque:
            st.caption(t("Résultat limité aux 200 premières lignes.", "Result limited to the first 200 rows."))
    if rep.sql:
        st.markdown(f"**{t('Requête exécutée', 'Query run')}**")
        st.code(rep.sql, language="sql")
    if rep.essais:
        with st.expander(t(f"Tentatives corrigées ({len(rep.essais)})", f"Corrected attempts ({len(rep.essais)})")):
            for s, err in rep.essais:
                st.code(s, language="sql")
                st.caption(err)


def onglet_bio(t, lang):
    q = _question(t, "rag", EXEMPLES_RAG[lang],
                  t("Question sur la carrière, la formation, les trophées : la réponse vient des biographies "
                    "Wikipédia indexées, avec les sources.",
                    "Question about career, academy, trophies: the answer comes from indexed Wikipedia "
                    "biographies, with sources."))
    if q:
        with st.spinner(t("Recherche dans les biographies...", "Searching biographies...")):
            try:
                st.session_state["rep_rag"] = rag.repondre(q, lang)
            except Exception as e:
                _erreur(t, e)
    rep = st.session_state.get("rep_rag")
    if not rep:
        return
    st.markdown(f"**{html.escape(rep.question)}**")
    st.markdown(rep.texte)
    if rep.sources:
        st.markdown(f"**{t('Sources', 'Sources')}**")
        for s in rep.sources:
            with st.expander(f"[{s.numero}] {s.player} · {s.section} · {s.score:.2f}"):
                st.write(s.texte)
                if s.url:
                    st.markdown(f"[{t('Article Wikipédia', 'Wikipedia article')}]({s.url})")


def bloc_rapport(t, lang, faits, cle):
    """Bouton + rapport de scouting d'un joueur (fiche ou page Assistant)."""
    ok, msg = _etat(t)
    if not ok:
        st.info(msg)
        return
    if st.button(t("Rédiger le rapport de scouting", "Write the scouting report"), key=f"btn_{cle}",
                 type="primary"):
        with st.spinner(t("Rédaction du rapport (30 s à 2 min selon l'ordinateur)...",
                          "Writing the report (30 s to 2 min depending on the computer)...")):
            try:
                st.session_state[f"rapport_{cle}"] = report.rediger(faits, lang)
            except Exception as e:
                _erreur(t, e)
    r = st.session_state.get(f"rapport_{cle}")
    if not r:
        st.caption(t("Le rapport est rédigé par un modèle local (Ollama) à partir des statistiques, des "
                     "percentiles, de l'estimation de valeur et des joueurs proches calculés par le projet.",
                     "The report is written by a local model (Ollama) from the stats, percentiles, value "
                     "estimate and similar players computed by the project."))
        return
    st.markdown(r.texte)
    if r.chiffres_non_verifies:
        st.warning(t("Chiffres absents des données fournies au modèle (à vérifier) : ",
                     "Numbers not found in the data given to the model (check them): ")
                   + ", ".join(r.chiffres_non_verifies))
    else:
        st.caption(t("Contrôle : tous les chiffres du rapport viennent des données.",
                     "Check: every number in the report comes from the data."))
    with st.expander(t("Faits donnés au modèle", "Facts given to the model")):
        st.text(r.faits)
    st.download_button(t("Télécharger (.md)", "Download (.md)"), r.texte,
                       file_name=f"rapport_{faits['joueur'].replace(' ', '_')}.md", key=f"dl_{cle}")


def page_assistant(t, lang, chercher_joueurs, faits_pour):
    st.markdown(
        f'<div class="hero"><div class="titre">{t("Assistant de scouting", "Scouting assistant")}</div>'
        f'<div class="ligne">' + t(
            "Questions en langage naturel sur la base, sur les biographies des joueurs, "
            "et rapports de scouting rédigés à partir des données du projet.",
            "Natural-language questions on the database and on player biographies, "
            "and scouting reports written from the project's data.") + '</div></div>',
        unsafe_allow_html=True)
    ok, msg = _etat(t)
    (st.caption if ok else st.warning)(msg if ok else msg + "  \n" + t(
        "Installation : https://ollama.com puis « ollama pull qwen2.5:7b » et « ollama pull bge-m3 ».",
        "Setup: https://ollama.com then `ollama pull qwen2.5:7b` and `ollama pull bge-m3`."))
    if not ok:
        return
    t_sql, t_bio, t_rap = st.tabs([t("Questions chiffrées (SQL)", "Numbers (SQL)"),
                                   t("Biographies (Wikipédia)", "Biographies (Wikipedia)"),
                                   t("Rapport de scouting", "Scouting report")])
    with t_sql:
        onglet_sql(t, lang)
    with t_bio:
        onglet_bio(t, lang)
    with t_rap:
        nom = st.text_input(t("Joueur", "Player"), key="rapport_recherche",
                            placeholder=t("Ex. : Saibari, Doku...", "E.g. Saibari, Doku..."))
        choix = chercher_joueurs(nom) if nom.strip() else []
        if nom.strip() and not choix:
            st.info(t("Aucun joueur trouvé.", "No player found."))
        if choix:
            tid = st.selectbox(t("Choisir", "Choose"), [c[0] for c in choix],
                               format_func=dict(choix).get, key="rapport_choix")
            faits = faits_pour(tid)
            if faits:
                bloc_rapport(t, lang, faits, f"assistant_{tid}")

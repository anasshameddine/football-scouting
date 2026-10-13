"""
Rapport de scouting rédigé par le modèle à partir de faits calculés par le projet.

Le modèle ne calcule rien : statistiques, percentiles, valeur, estimation et joueurs proches
lui sont donnés. Après la rédaction, chaque nombre du rapport est comparé aux faits :
ceux qui n'y figurent pas sont signalés (risque d'invention).
"""

import re
from dataclasses import dataclass, field

from . import llm

SECTIONS = {
    "fr": ["Résumé", "Profil et style de jeu", "Points forts", "Points à surveiller",
           "Évolution sur les dernières saisons", "Valeur et marché", "Joueurs comparables",
           "Verdict du scout"],
    "en": ["Summary", "Profile and playing style", "Strengths", "Areas to watch",
           "Recent seasons", "Value and market", "Comparable players", "Scout's verdict"],
}


@dataclass
class Rapport:
    texte: str
    faits: str
    chiffres_non_verifies: list = field(default_factory=list)


def _f(x, d=1):
    return "?" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))


def faits_texte(f):
    """Faits lisibles par le modèle (et par le contrôle des chiffres)."""
    L = [f"Joueur : {f['joueur']}"]
    for cle, lib in [("age", "Âge"), ("club", "Club"), ("championnat", "Championnat"), ("poste", "Poste"),
                     ("pied", "Pied fort"), ("taille_cm", "Taille (cm)"), ("nationalite", "Nationalité"),
                     ("selections", "Sélections internationales"), ("fin_contrat", "Fin de contrat"),
                     ("archetype", "Archétype statistique"), ("score_global", "Score global (sur 100)"),
                     ("valeur_actuelle_meur", "Valeur Transfermarkt actuelle (M€)"),
                     ("valeur_max_meur", "Valeur maximale en carrière (M€)"),
                     ("estimation_modele_meur", "Valeur estimée par le modèle (M€)"),
                     ("fourchette_meur", "Fourchette à 80 % de l'estimation (M€)")]:
        if f.get(cle) not in (None, ""):
            L.append(f"{lib} : {_f(f[cle])}")
    if f.get("prudence"):
        L.append("Remarque : au-dessus de 50 M€, le modèle sous-estime en moyenne de 30 % les joueurs "
                 "les plus chers ; l'estimation est prudente.")
    if f.get("points_forts"):
        L.append("Meilleurs percentiles dans son poste (statistique par 90 min : valeur, percentile sur 100) :")
        L += [f"  - {n} : {_f(v, 2)}, percentile {p}" for n, v, p in f["points_forts"]]
    if f.get("points_faibles"):
        L.append("Percentiles les plus bas dans son poste :")
        L += [f"  - {n} : {_f(v, 2)}, percentile {p}" for n, v, p in f["points_faibles"]]
    if f.get("saisons"):
        L.append("Saisons (xG et xA seulement dans les 5 grands championnats) :")
        L += [f"  - {s['saison']}, {s['club']} : {s['minutes']} min, {s['matchs']} matchs, {s['buts']} buts, "
              f"{s['passes']} passes décisives"
              + (f", xG {_f(s['xg'])}, xA {_f(s.get('xa'))}" if s.get("xg") is not None else "")
              for s in f["saisons"]]
    if f.get("similaires"):
        L.append("Joueurs au profil statistique le plus proche (similarité %, valeur M€) :")
        L += [f"  - {n} ({c}) : {s} %" + (f", {_f(v)} M€" if v is not None else "")
              for n, c, s, v in f["similaires"]]
    if f.get("biographie"):
        L.append(f"Biographie (Wikipédia) : {f['biographie']}")
    return "\n".join(L)


def _nombres(texte):
    return [x.replace(",", ".") for x in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?", texte)]


def chiffres_inventes(rapport, faits):
    """Nombres du rapport absents des faits (les petits entiers et les années sont ignorés)."""
    connus = set()
    for x in _nombres(faits):
        v = float(x)
        connus |= {x, f"{v:g}", f"{v:.0f}", f"{v:.1f}", f"{round(v)}"}
    suspects = []
    for x in _nombres(rapport):
        v = float(x)
        if (v.is_integer() and v <= 10) or 1990 <= v <= 2040:
            continue
        if x not in connus and f"{v:g}" not in connus and f"{v:.1f}" not in connus:
            suspects.append(x)
    return sorted(set(suspects), key=float)


def rediger(faits, langue="fr", chat=None):
    chat = chat or llm.chat
    texte_faits = faits_texte(faits)
    titres = "\n".join(f"## {s}" for s in SECTIONS[langue])
    consigne = ("Rédige en français." if langue == "fr" else "Write in English.")
    texte = chat([
        {"role": "system", "content":
         "Tu es recruteur (scout) dans un club de football. Tu rédiges des rapports courts, concrets et "
         "honnêtes. Tu utilises UNIQUEMENT les faits fournis : n'invente aucun chiffre, aucun club, aucun "
         "trophée. Un percentile de 90 signifie « meilleur que 90 % des joueurs de son poste »."},
        {"role": "user", "content":
         f"Faits sur le joueur :\n{texte_faits}\n\n{consigne} Utilise exactement ces sections, en Markdown :\n"
         f"{titres}\n\nChaque section fait 2 à 4 phrases ou puces. Dans « Valeur et marché », compare la "
         "valeur actuelle et l'estimation du modèle. Dans le verdict, dis pour quel type de club et quel "
         "budget ce joueur est une bonne cible, et ce qu'il faut vérifier en le regardant jouer."}],
        temperature=0.2).strip()
    return Rapport(texte, texte_faits, chiffres_inventes(texte, texte_faits))

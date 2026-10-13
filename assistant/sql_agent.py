"""
Agent « texte vers SQL » : une question en français ou en anglais devient une requête sur le schéma gold.

Sécurité, en trois couches :
1. vérification de la requête générée (une seule instruction SELECT, tables autorisées uniquement) ;
2. exécution dans une transaction en lecture seule, avec un délai maximum ;
3. conseillé : un rôle PostgreSQL qui n'a que le droit SELECT (assistant/sql/role_lecture.sql).

    python -m assistant.sql_agent "Top 5 des buteurs marocains cette saison"
"""

import re
import sys
from dataclasses import dataclass, field

import pandas as pd
import sqlglot
from sqlalchemy import create_engine
from sqlglot import exp

from . import llm, schema
from .config import DB_URL_LECTURE, MAX_LIGNES, TIMEOUT_SQL_MS

MOTS_INTERDITS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|call|do|execute|"
    r"vacuum|comment|lock|set|reset|listen|notify|prepare|refresh|reindex|cluster|merge|into|"
    r"pg_sleep|pg_read_file|pg_read_binary_file|pg_ls_dir|lo_import|lo_export|dblink|"
    r"set_config|current_setting)\b", re.I)


class RequeteRefusee(ValueError):
    """La requête générée ne respecte pas les règles de sécurité."""


@dataclass
class Reponse:
    question: str
    sql: str | None = None
    donnees: pd.DataFrame | None = None
    texte: str | None = None
    tronque: bool = False
    erreur: str | None = None
    essais: list = field(default_factory=list)   # [(sql, erreur), ...] des tentatives ratées


# ------------------------------------------------------------------ extraction et vérification
def extraire_sql(reponse_llm):
    """Récupère la requête dans la réponse du modèle (bloc ```sql, bloc ``` ou texte brut)."""
    m = re.search(r"```(?:sql)?\s*(.*?)```", reponse_llm, re.S | re.I)
    sql = m.group(1) if m else reponse_llm
    m = re.search(r"\b(with|select)\b", sql, re.I)
    if m:
        sql = sql[m.start():]
    return sql.strip().rstrip(";").strip()


def _sans_commentaires_ni_textes(sql):
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def verifier(sql, tables=schema.TABLES_AUTORISEES):
    """Lève RequeteRefusee si la requête n'est pas une lecture simple des tables autorisées."""
    nu = _sans_commentaires_ni_textes(sql).strip().rstrip(";")
    if ";" in nu:
        raise RequeteRefusee("Une seule requête est autorisée.")
    if not re.match(r"^\s*(select|with)\b", nu, re.I):
        raise RequeteRefusee("Seules les requêtes SELECT sont autorisées.")
    m = MOTS_INTERDITS.search(nu)
    if m:
        raise RequeteRefusee(f"Mot interdit dans la requête : {m.group(0).upper()}.")
    try:
        arbre = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        raise RequeteRefusee(f"Requête illisible : {str(e).splitlines()[0]}") from e
    if not isinstance(arbre, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise RequeteRefusee("Seules les requêtes SELECT sont autorisées.")
    ctes = {c.alias_or_name.lower() for c in arbre.find_all(exp.CTE)}
    autorisees = {x.lower() for x in tables}
    for tb in arbre.find_all(exp.Table):
        nom = f"{tb.db}.{tb.name}".lower() if tb.db else tb.name.lower()
        if nom not in autorisees and nom not in ctes:
            raise RequeteRefusee(f"Table non autorisée : {nom}.")
    return sql


def corriger_round(sql):
    """round(x, n) n'existe pas en PostgreSQL pour un double precision : on convertit x en numeric.
    Erreur la plus fréquente des petits modèles, corrigée sans repasser par le modèle."""
    if not re.search(r"\bround\s*\(", sql, re.I):
        return sql
    try:
        arbre = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.errors.ParseError:
        return sql
    modifie = False
    for r in arbre.find_all(exp.Round):
        x = r.this
        if r.args.get("decimals") is not None and not (isinstance(x, exp.Cast) and x.to.is_type("decimal")):
            r.set("this", exp.Cast(this=x.copy(), to=exp.DataType.build("numeric")))
            modifie = True
    return arbre.sql(dialect="postgres", pretty=True) if modifie else sql


# ------------------------------------------------------------------ exécution
_moteurs = {}


def executer(sql, db_url=None):
    """Exécute en lecture seule avec délai maximum ; renvoie (DataFrame, tronqué ?)."""
    db_url = db_url or DB_URL_LECTURE
    if db_url not in _moteurs:
        _moteurs[db_url] = create_engine(db_url, pool_pre_ping=True)
    brut = _moteurs[db_url].raw_connection()
    try:
        cur = brut.cursor()
        cur.execute("set transaction read only")
        cur.execute(f"set local statement_timeout = {int(TIMEOUT_SQL_MS)}")
        cur.execute(sql)                          # sans paramètres : aucun remplacement de « % »
        colonnes = [c.name for c in cur.description]
        lignes = cur.fetchmany(MAX_LIGNES + 1)
    finally:
        brut.rollback()
        brut.close()
    return pd.DataFrame(lignes[:MAX_LIGNES], columns=colonnes), len(lignes) > MAX_LIGNES


# ------------------------------------------------------------------ génération
_contexte = {}


def contexte(db_url=None):
    db_url = db_url or DB_URL_LECTURE
    if db_url not in _contexte:
        _contexte[db_url] = schema.contexte(db_url)
    return _contexte[db_url]


def messages(question, ctx_texte, derniere):
    msgs = [{"role": "system",
             "content": "Tu écris des requêtes SQL PostgreSQL pour une base de scouting football.\n\n"
                        + ctx_texte}]
    for q, s in schema.EXEMPLES:
        msgs += [{"role": "user", "content": q},
                 {"role": "assistant", "content": f"```sql\n{s.format(derniere=derniere)}\n```"}]
    msgs.append({"role": "user", "content": question})
    return msgs


def generer_et_executer(question, db_url=None, chat=None, essais_max=3):
    """Génère la requête, la vérifie, l'exécute ; en cas d'erreur, renvoie l'erreur au modèle pour correction."""
    chat = chat or llm.chat
    ctx_texte, valeurs = contexte(db_url)
    msgs = messages(question, ctx_texte, valeurs["derniere"])
    rep = Reponse(question)
    vide_signale = False
    for _ in range(essais_max):
        brut = chat(msgs)
        sql = corriger_round(extraire_sql(brut))
        msgs.append({"role": "assistant", "content": f"```sql\n{sql}\n```"})
        try:
            verifier(sql)
            df, tronque = executer(sql, db_url)
        except RequeteRefusee as e:
            rep.essais.append((sql, str(e)))
            msgs.append({"role": "user", "content": f"Requête refusée : {e} Réécris-la."})
            continue
        except Exception as e:  # erreur PostgreSQL : colonne inconnue, type, délai dépassé...
            err = str(getattr(e, "pgerror", None) or e).strip().splitlines()[0]
            rep.essais.append((sql, err))
            msgs.append({"role": "user", "content": f"Erreur PostgreSQL : {err}\nCorrige la requête."})
            continue
        if df.empty and not vide_signale:
            # souvent un nom mal écrit ou un filtre trop strict : une seule relance
            vide_signale = True
            rep.essais.append((sql, "0 ligne"))
            msgs.append({"role": "user", "content":
                         "La requête renvoie 0 ligne. Vérifie l'orthographe des noms (minuscules sans accents, "
                         "avec ilike '%...%'), la saison et les valeurs exactes des championnats et postes. "
                         "Si la requête est juste, renvoie-la telle quelle."})
            continue
        rep.sql, rep.donnees, rep.tronque = sql, df, tronque
        return rep
    # dernier essai vide mais valide : on le garde quand même
    if rep.essais and rep.essais[-1][1] == "0 ligne":
        rep.sql, rep.donnees = rep.essais.pop()[0], pd.DataFrame()
        return rep
    rep.erreur = rep.essais[-1][1] if rep.essais else "Aucune requête générée."
    rep.sql = rep.essais[-1][0] if rep.essais else None
    return rep


def formuler(question, df, langue="fr", chat=None):
    """Phrase courte qui répond à la question à partir du tableau (le modèle ne voit que ces chiffres)."""
    chat = chat or llm.chat
    if df is None or df.empty:
        return ("Aucun résultat dans la base pour cette question." if langue == "fr"
                else "No result in the database for this question.")
    tableau = df.head(15).to_markdown(index=False)
    consigne = ("Réponds en français, en 1 à 3 phrases, uniquement à partir du tableau. "
                if langue == "fr" else "Answer in English, in 1 to 3 sentences, using only the table. ")
    return chat([{"role": "user", "content":
                  f"Question : {question}\n\nRésultat de la requête :\n{tableau}\n\n{consigne}"
                  "N'invente aucun chiffre. Les montants en euros peuvent être écrits en millions (M€)."}],
                temperature=0.1).strip()


def repondre(question, langue="fr", db_url=None, chat=None):
    rep = generer_et_executer(question, db_url, chat)
    if rep.erreur is None:
        rep.texte = formuler(question, rep.donnees, langue, chat)
    return rep


if __name__ == "__main__":
    r = repondre(" ".join(sys.argv[1:]) or "Top 5 des buteurs marocains cette saison")
    print(r.sql, "\n")
    print(r.erreur or r.donnees.to_string(index=False))
    print("\n", r.texte)

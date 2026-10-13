"""
RAG sur les biographies Wikipédia des joueurs (pgvector + embeddings Ollama).

1. Indexation (une fois, puis de temps en temps) :
       python -m assistant.rag --limite 500          # Marocains d'abord, puis par valeur décroissante
   Pour chaque joueur : page Wikipédia trouvée avec les mêmes contrôles d'homonymes que la fiche,
   article complet découpé en passages, un vecteur par passage, stockage dans rag.bio_passages.
   Les articles téléchargés sont gardés dans data/rag/ : relancer ne retélécharge rien.

2. Question :
       python -m assistant.rag --question "Où a été formé Bilal El Khannouss ?"
   Si la question cite un joueur de la base, la recherche se limite à sa biographie
   (indexée à la volée si elle manque) ; sinon elle porte sur toutes les biographies.

3. État de l'index :
       python -m assistant.rag --statut Le modèle répond en citant ses sources [1], [2]...
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field

import requests
from sqlalchemy import create_engine, text

from . import llm
from .config import DB_URL, ROOT

sys.path.insert(0, str(ROOT / "app"))
from wiki import chercher, ua  # noqa: E402

CACHE = ROOT / "data" / "rag"
SECTIONS_EXCLUES = {"references", "external links", "see also", "notes", "bibliography",
                    "further reading", "career statistics", "statistics",
                    "références", "liens externes", "voir aussi", "notes et références",
                    "bibliographie", "statistiques"}
TAILLE, CHEVAUCHEMENT = 1100, 150     # caractères par passage


def _norm(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


# ------------------------------------------------------------------ Wikipédia
class GetPoli:
    """requests.get qui respecte Wikipédia : au plus une requête par seconde, et en cas de
    réponse 429 (trop de requêtes) attend le délai demandé (Retry-After) avant de réessayer."""

    def __init__(self, get=requests.get, intervalle=1.0, essais=5):
        self.get, self.intervalle, self.essais, self.dernier = get, intervalle, essais, 0.0

    def __call__(self, url, **kw):
        for k in range(self.essais):
            attente = self.intervalle - (time.time() - self.dernier)
            if attente > 0:
                time.sleep(attente)
            self.dernier = time.time()
            r = self.get(url, **kw)
            if getattr(r, "status_code", 200) != 429:
                return r
            delai = r.headers.get("Retry-After", "") if hasattr(r, "headers") else ""
            delai = min(int(delai), 120) if str(delai).isdigit() else 15 * (k + 1)
            print(f"  Wikipédia demande de ralentir : pause de {delai} s")
            time.sleep(delai)
        return r


def article_complet(titre, lang, get=requests.get):
    """Texte brut de l'article, avec les titres de section au format « == Titre == »."""
    r = get(f"https://{lang}.wikipedia.org/w/api.php", headers=ua(), timeout=15,
            params={"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
                    "exsectionformat": "wiki", "titles": titre, "format": "json"})
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    return next(iter(pages.values()), {}).get("extract", "") if pages else ""


def decouper(texte, taille=TAILLE, chevauchement=CHEVAUCHEMENT):
    """[(section, passage), ...] : sections inutiles retirées, passages coupés entre deux phrases."""
    morceaux, section, exclu = [], "Introduction", False
    blocs = re.split(r"^(={2,}\s*.+?\s*={2,})\s*$", texte, flags=re.M)
    for bloc in blocs:
        titre = re.match(r"^(={2,})\s*(.+?)\s*={2,}$", bloc.strip())
        if titre:
            niveau, section = len(titre.group(1)), titre.group(2)
            if niveau == 2:                    # une section exclue entraîne ses sous-sections
                exclu = _norm(section) in SECTIONS_EXCLUES
            elif _norm(section) in SECTIONS_EXCLUES:
                exclu = True
            continue
        if exclu or not bloc.strip():
            continue
        corps = re.sub(r"\s+", " ", bloc).strip()
        debut = 0
        while debut < len(corps):
            fin = min(len(corps), debut + taille)
            if fin < len(corps):                       # recule jusqu'à la fin d'une phrase
                point = corps.rfind(". ", debut + taille // 2, fin)
                fin = point + 1 if point > 0 else fin
            morceau = corps[debut:fin].strip()
            if len(morceau) > 80:
                morceaux.append((section, morceau))
            if fin >= len(corps):
                break
            debut = max(fin - chevauchement, debut + 1)
    return morceaux


def biographie_joueur(j, lang, get=requests.get, essais=3):
    """Article Wikipédia d'un joueur (dict) ou None s'il n'a pas de page ; utilise le cache disque.
    Une erreur réseau est retentée puis levée : elle n'est jamais mémorisée comme « pas de page »."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{lang}_{int(j['tm_player_id'])}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("absent"):
            return None
        if d.get("texte"):
            return d
        # fichier vide d'une ancienne version : peut venir d'une coupure réseau, on réessaie
    for k in range(essais):
        try:
            page = chercher(j["player"], j["born"], lang, club=j["team"], get=get, lever=True)
            d = {**page, "texte": article_complet(page["titre"], lang, get)} if page else {"absent": True}
            break
        except (requests.RequestException, ValueError):
            if k == essais - 1:
                raise
            time.sleep(2 * (k + 1))
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return None if d.get("absent") else d


# ------------------------------------------------------------------ base vectorielle
def _vecteur(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def creer_table(engine, dim, reset=False):
    with engine.begin() as cx:
        cx.execute(text("create extension if not exists vector"))
        cx.execute(text("create schema if not exists rag"))
        if reset:
            cx.execute(text("drop table if exists rag.bio_passages"))
        cx.execute(text(f"""
            create table if not exists rag.bio_passages (
                id bigserial primary key,
                tm_player_id bigint not null,
                player text not null,
                titre text, url text, lang text, section text, numero int,
                texte text not null,
                embedding vector({int(dim)}) not null)"""))
        existante = cx.execute(text(
            "select atttypmod from pg_attribute where attrelid = 'rag.bio_passages'::regclass "
            "and attname = 'embedding'")).scalar()
        if existante != dim:
            raise SystemExit(f"rag.bio_passages contient des vecteurs de dimension {existante} et le modèle "
                             f"en produit {dim} : relance avec --reset.")
        cx.execute(text("create index if not exists bio_passages_joueur on rag.bio_passages (tm_player_id)"))


def joueurs_a_indexer(engine, limite):
    """Marocains d'abord, puis les joueurs les plus chers, avec leur dernier club."""
    sql = """
        select distinct on (p.tm_player_id) p.tm_player_id, p.player, p.born, f.team,
               p.is_moroccan, p.tm_value_eur
        from gold.dim_player p
        join gold.fact_player_season f on f.player_key = p.player_key
        where p.tm_player_id is not null
        order by p.tm_player_id, f.season desc"""
    with engine.connect() as cx:
        rows = [dict(r._mapping) for r in cx.execute(text(sql))]
    rows.sort(key=lambda r: (not r["is_moroccan"], -(r["tm_value_eur"] or 0)))
    return rows[:limite]


def indexer_joueur(engine, j, lang="en", get=requests.get, embed=None):
    """Télécharge, découpe et indexe la biographie d'un joueur. Renvoie le nombre de passages (0 si aucune page)."""
    embed = embed or llm.embed
    bio = biographie_joueur(j, lang, get)
    if not (bio and bio.get("texte")):
        return 0
    passages = decouper(bio["texte"])[:40]
    if not passages:
        return 0
    # l'en-tête (joueur + section) aide la recherche à relier un passage à son joueur
    vecteurs = embed([f"{j['player']} ({bio['titre']}), {s} : {p}" for s, p in passages])
    with engine.begin() as cx:
        cx.execute(text("delete from rag.bio_passages where tm_player_id = :id and lang = :l"),
                   {"id": j["tm_player_id"], "l": lang})
        cx.execute(text("""
            insert into rag.bio_passages
                (tm_player_id, player, titre, url, lang, section, numero, texte, embedding)
            values (:id, :player, :titre, :url, :lang, :section, :numero, :texte, cast(:v as vector))"""),
            [{"id": j["tm_player_id"], "player": j["player"], "titre": bio["titre"],
              "url": bio["url"], "lang": lang, "section": s, "numero": k, "texte": p,
              "v": _vecteur(v)} for k, ((s, p), v) in enumerate(zip(passages, vecteurs))])
    return len(passages)


def indexer(limite=500, lang="en", reset=False, get=requests.get, embed=None, db_url=None):
    embed = embed or llm.embed
    get = GetPoli(get)
    engine = create_engine(db_url or DB_URL)
    creer_table(engine, len(embed(["test"])[0]), reset)
    deja = _indexes(engine)
    joueurs = [j for j in joueurs_a_indexer(engine, limite) if j["tm_player_id"] not in deja]
    print(f"{len(deja)} joueurs déjà indexés, {len(joueurs)} à traiter.")
    n_ok, n_passages, n_reseau = 0, 0, 0
    for i, j in enumerate(joueurs, 1):
        try:
            n = indexer_joueur(engine, j, lang, get, embed)
            n_ok, n_passages = n_ok + (n > 0), n_passages + n
        except (requests.RequestException, ValueError) as e:
            n_reseau += 1
            print(f"  réseau : {j['player']} non traité ({e.__class__.__name__}: {str(e)[:80]})")
        if i % 25 == 0 or i == len(joueurs):
            print(f"  {i}/{len(joueurs)} joueurs traités : {n_ok} biographies, {n_passages} passages, "
                  f"{n_reseau} erreurs réseau")
    with engine.begin() as cx:
        cx.execute(text("create index if not exists bio_passages_vecteur on rag.bio_passages "
                        "using hnsw (embedding vector_cosine_ops)"))
    print(f"Terminé : {n_ok} biographies ajoutées ({n_passages} passages).")
    if n_reseau:
        print(f"{n_reseau} joueurs non traités à cause du réseau : relance la même commande, "
              "ils seront repris (les autres ne sont pas retéléchargés).")


def _indexes(engine):
    with engine.connect() as cx:
        return {r[0] for r in cx.execute(text("select distinct tm_player_id from rag.bio_passages"))}


def statut(db_url=None):
    """Résumé de l'index : joueurs, passages, Marocains couverts, Marocains sans page trouvée."""
    engine = create_engine(db_url or DB_URL)
    with engine.connect() as cx:
        n_j, n_p = cx.execute(text("select count(distinct tm_player_id), count(*) from rag.bio_passages")).one()
        ma = cx.execute(text("""
            select p.tm_player_id, p.player, (b.tm_player_id is not null) as indexe
            from gold.dim_player p
            left join (select distinct tm_player_id from rag.bio_passages) b using (tm_player_id)
            where p.is_moroccan and p.tm_player_id is not null order by p.tm_value_eur desc nulls last""")).all()
    print(f"{n_j} joueurs indexés, {n_p} passages.")
    fichiers = list(CACHE.glob("*.json")) if CACHE.exists() else []
    absents = sum('"absent"' in f.read_text(encoding="utf-8") for f in fichiers)
    print(f"Cache Wikipédia : {len(fichiers)} joueurs consultés, dont {absents} sans page trouvée.")
    print(f"Marocains indexés : {sum(r.indexe for r in ma)} / {len(ma)}")
    absents = [r.player for r in ma if not r.indexe]
    if absents:
        print("Marocains sans biographie (pas de page trouvée, ou pas encore traités) :")
        print("  " + ", ".join(absents[:40]) + (" ..." if len(absents) > 40 else ""))


# ------------------------------------------------------------------ recherche et réponse
@dataclass
class Source:
    numero: int
    player: str
    titre: str
    url: str
    section: str
    texte: str
    score: float


@dataclass
class ReponseRag:
    question: str
    texte: str = ""
    sources: list = field(default_factory=list)
    joueurs: list = field(default_factory=list)   # joueurs reconnus dans la question


def joueurs_cites(question, index):
    """Identifiants des joueurs indexés dont le nom (complet, ou nom de famille) est dans la question.
    index : [(tm_player_id, player), ...]"""
    q = f" {re.sub(r'[^a-z0-9 ]', ' ', _norm(question))} "
    complets, familles = [], []
    for tid, nom in index:
        n = re.sub(r"[^a-z0-9 ]", " ", _norm(nom)).split()
        if not n:
            continue
        if f" {' '.join(n)} " in q:
            complets.append(tid)
        elif len(n) > 1 and len(n[-1]) >= 4 and f" {n[-1]} " in q:
            familles.append(tid)
    return complets or familles


def _joueurs_base(engine):
    """Tous les joueurs de la base avec leur dernier club (pour reconnaître un nom dans une question)."""
    with engine.connect() as cx:
        return [dict(r._mapping) for r in cx.execute(text("""
            select distinct on (p.tm_player_id) p.tm_player_id, p.player, p.born, f.team
            from gold.dim_player p join gold.fact_player_season f on f.player_key = p.player_key
            where p.tm_player_id is not null
            order by p.tm_player_id, f.season desc"""))]


_moteurs = {}


def _moteur(db_url):
    db_url = db_url or DB_URL
    if db_url not in _moteurs:
        _moteurs[db_url] = create_engine(db_url, pool_pre_ping=True)
    return _moteurs[db_url]


def rechercher(question, k=6, db_url=None, embed=None, ids=None):
    """Passages les plus proches de la question ; limités aux joueurs « ids » s'ils sont donnés."""
    embed = embed or llm.embed
    filtre = "where tm_player_id = any(:ids)" if ids else ""
    with _moteur(db_url).connect() as cx:
        rows = cx.execute(text(f"""
            select player, titre, url, section, texte,
                   1 - (embedding <=> cast(:v as vector)) as score
            from rag.bio_passages {filtre}
            order by embedding <=> cast(:v as vector)
            limit :k"""), {"v": _vecteur(embed([question])[0]), "ids": list(ids or []), "k": k}).fetchall()
    return [Source(i, *r) for i, r in enumerate(rows, 1)]


def repondre(question, langue="fr", k=6, db_url=None, chat=None, embed=None, get=requests.get):
    """Si la question cite un joueur de la base : sa biographie est indexée à la volée si besoin,
    et la recherche se limite à lui. Sinon : recherche dans toutes les biographies."""
    chat = chat or llm.chat
    engine = _moteur(db_url)
    fr = langue == "fr"
    joueurs = _joueurs_base(engine)
    ids = joueurs_cites(question, [(j["tm_player_id"], j["player"]) for j in joueurs])
    if len(ids) > 5:          # nom de famille trop courant : on ne restreint pas la recherche
        ids = []
    rep = ReponseRag(question, joueurs=ids)
    if ids:
        creer_table(engine, len((embed or llm.embed)(["test"])[0]))   # table créée si première utilisation
        deja = _indexes(engine)
        par_id = {j["tm_player_id"]: j for j in joueurs}
        for tid in [i for i in ids if i not in deja]:
            try:
                indexer_joueur(engine, par_id[tid], "en", GetPoli(get, intervalle=0.2, essais=2), embed)
            except (requests.RequestException, ValueError):
                pass
        ids = [i for i in ids if i in _indexes(engine)]
        if not ids:
            noms = ", ".join(par_id[i]["player"] for i in rep.joueurs)
            rep.texte = (f"Pas de biographie Wikipédia trouvée pour {noms} (page absente, homonyme non "
                         "confirmé, ou pas de connexion)." if fr else
                         f"No Wikipedia biography found for {noms} (no page, unconfirmed namesake, "
                         "or no connection).")
            return rep
    # un seul joueur visé : on lit davantage de passages (formation, clubs, sélection sont dans des sections différentes)
    rep.sources = rechercher(question, max(k, 12) if len(ids) == 1 else k, db_url, embed, ids)
    if not rep.sources:
        rep.texte = ("Aucune biographie indexée. Lance d'abord : python -m assistant.rag --limite 500"
                     if fr else "No biography indexed yet. Run: python -m assistant.rag --limite 500")
        return rep
    extraits = "\n\n".join(f"[{s.numero}] {s.player}, section « {s.section} » :\n{s.texte}" for s in rep.sources)
    consigne = ("Réponds en français." if fr else "Answer in English.")
    rep.texte = chat([
        {"role": "system", "content":
         "Tu es un assistant de scouting football. Tu réponds uniquement à partir des extraits de "
         "biographies Wikipédia fournis. Après chaque information, cite l'extrait entre crochets, ex. [2]. "
         "Si les extraits ne contiennent pas la réponse, dis-le clairement au lieu de deviner. "
         "Ne mélange pas deux joueurs différents."},
        {"role": "user", "content": f"Extraits :\n\n{extraits}\n\nQuestion : {question}\n\n{consigne} "
                                    "Réponse courte (3 à 6 phrases)."}], temperature=0.1).strip()
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limite", type=int, default=500, help="nombre de joueurs à indexer")
    ap.add_argument("--langue", default="en", choices=["en", "fr"], help="Wikipédia utilisé")
    ap.add_argument("--reset", action="store_true", help="vide la table avant d'indexer")
    ap.add_argument("--question", help="pose une question au lieu d'indexer")
    ap.add_argument("--statut", action="store_true", help="résumé de l'index (joueurs, Marocains couverts)")
    ap.add_argument("--tester", metavar="NOM", help="diagnostic : recherche Wikipédia d'un joueur de la base")
    a = ap.parse_args()
    if a.statut:
        sys.exit(statut())
    if a.tester:
        cible = _norm(a.tester)
        trouves = [j for j in _joueurs_base(_moteur(None)) if cible in _norm(j["player"])][:3]
        if not trouves:
            sys.exit(f"Aucun joueur « {a.tester} » dans la base.")
        for j in trouves:
            print(f"{j['player']} (né en {j['born']}, {j['team']}, id {j['tm_player_id']})")
            try:
                page = chercher(j["player"], j["born"], a.langue, club=j["team"], lever=True)
                print("  page :", page["url"] if page else "aucune page retenue (homonyme non confirmé)")
            except Exception as e:
                print(f"  erreur réseau : {type(e).__name__}: {e}")
        sys.exit()
    ok, msg = llm.etat()
    if not ok:
        sys.exit(msg)
    if a.question:
        r = repondre(a.question)
        print(r.texte, "\n")
        for s in r.sources:
            print(f"[{s.numero}] {s.player} / {s.section} ({s.score:.2f}) {s.url}")
    else:
        indexer(a.limite, a.langue, a.reset)

"""
Description du schéma gold donnée au modèle pour écrire du SQL.

On ne lui donne pas toutes les tables : seulement celles utiles aux questions de scouting,
avec le sens des colonnes et les valeurs possibles (championnats, saisons, postes).
Les listes de valeurs sont lues dans la base au démarrage, pour rester justes après un rechargement.
"""

from sqlalchemy import create_engine, text

TABLES_AUTORISEES = ("gold.dim_player", "gold.fact_player_season", "gold.fact_valuation",
                     "gold.dim_league", "gold.dim_season", "gold.dim_club", "ml.valeur_predite")

SCHEMA = """\
-- Une ligne par joueur. Clé : player_key.
gold.dim_player(
  player_key text, player text,           -- nom affiché, ex. 'Kylian Mbappé'
  player_clean text,                      -- nom en minuscules SANS accents, ex. 'kylian mbappe' : utiliser pour chercher un joueur
  born numeric,                           -- année de naissance
  nation_code text,                       -- code pays FBref, ex. 'MAR', 'FRA', 'ESP'
  is_moroccan boolean,                    -- joueur marocain (nationalité ou sélection)
  tm_player_id bigint,                    -- identifiant Transfermarkt
  tm_position text,                       -- 'Attack', 'Midfield', 'Defender', 'Goalkeeper'
  tm_sub_position text,                   -- poste précis, valeurs : {postes}
  tm_foot text,                           -- 'left', 'right', 'both'
  tm_height_cm double precision, tm_contract_end date, tm_citizenship text,
  tm_intl_caps double precision,          -- sélections en équipe nationale
  tm_value_eur double precision,          -- valeur Transfermarkt actuelle (euros)
  tm_peak_value_eur double precision      -- plus haute valeur de carrière (euros)
)

-- Une ligne par joueur et par saison (statistiques de la saison). Clé : (player_key, season).
gold.fact_player_season(
  player_key text, season text,           -- season codée sur 4 chiffres : {saisons}
  saison_label text,                      -- ex. '2025-2026'
  team text, league text,                 -- club et championnat, league parmi : {ligues}
  teams_all text, n_clubs bigint,         -- tous les clubs de la saison si transfert en cours de saison
  age numeric,                            -- âge pendant la saison
  pos_main text,                          -- 'GK', 'DF', 'MF', 'FW'
  playing_time_min numeric, playing_time_mp numeric, playing_time_starts numeric,  -- minutes, matchs, titularisations
  performance_gls numeric, performance_ast numeric,          -- buts, passes décisives
  performance_g_minus_pk numeric, performance_pk numeric,    -- buts hors penalty, penalties marqués
  performance_crdy numeric, performance_crdr numeric,        -- cartons jaunes, rouges
  performance_int numeric, performance_tklw numeric,         -- interceptions, tacles gagnés
  performance_crs numeric, performance_fld numeric, performance_fls numeric,  -- centres, fautes subies, commises
  standard_sh numeric, standard_sot numeric,                 -- tirs, tirs cadrés
  us_xg double precision, us_xa double precision, us_np_xg double precision,  -- xG, xA, xG hors penalty
  us_shots numeric, us_key_passes numeric,                   -- tirs et passes clés (Understat)
  us_xg_chain double precision, us_xg_buildup double precision,
  valeur_fin_saison_eur bigint            -- valeur Transfermarkt au 30 juin de la saison (euros)
)
-- Chaque statistique existe aussi « par 90 minutes » avec le suffixe _p90 (ex. performance_gls_p90, us_xg_p90).
-- Les colonnes us_* (Understat) ne sont remplies que pour les 5 grands championnats : NULL ailleurs.

-- Historique des valeurs Transfermarkt (plusieurs dates par joueur).
gold.fact_valuation(player_key text, tm_player_id bigint, date_valeur date, valeur_eur bigint)

-- Valeur prédite par le modèle XGBoost, une ligne par joueur et saison (au moins 450 minutes, hors gardiens).
ml.valeur_predite(
  player_key text, player text, team text, league text, season text, saison_label text,
  age double precision, playing_time_min double precision, is_moroccan boolean, tm_sub_position text,
  tm_player_id double precision,
  valeur_reelle_eur double precision,     -- valeur Transfermarkt au 30 juin
  valeur_predite_eur double precision,    -- valeur estimée par le modèle
  valeur_predite_basse_eur double precision, valeur_predite_haute_eur double precision,  -- fourchette à 80 %
  ecart_pct double precision              -- (prédite / réelle - 1) * 100 : positif = joueur sous-coté
)

gold.dim_league(league text, tm_competition text, pays text, est_big5 boolean)
gold.dim_season(season text, saison_label text, annee_debut integer, fin_saison date)
gold.dim_club(club_key text, club text, league text)
"""

REGLES = """\
Règles :
- PostgreSQL uniquement. Une seule requête SELECT (ou WITH ... SELECT). Jamais d'INSERT, UPDATE, DELETE, CREATE, DROP.
- N'utilise que les tables et colonnes listées ci-dessus.
- Joindre un joueur à ses saisons : gold.fact_player_season f join gold.dim_player p on p.player_key = f.player_key.
- « Cette saison », « actuellement », « en ce moment » = la saison la plus récente : f.season = '{derniere}'.
- Chercher un joueur par son nom : p.player_clean ilike '%nom en minuscules sans accents%'.
- Marocains : p.is_moroccan.
- Pour classer des statistiques par 90 minutes, garde seulement les joueurs avec au moins 900 minutes
  (f.playing_time_min >= 900), sauf si la question précise autre chose.
- Les montants sont en euros. Pour les afficher en millions : round(x / 1e6::numeric, 1).
- Avant round() sur une colonne double precision ou une division, convertis en numeric : round((a / b)::numeric, 2).
- Quand tu listes des joueurs, affiche le nom (player), le club (team) et le championnat (league).
- Pour un « top » sans nombre précisé, limite à 10 lignes et trie dans l'ordre demandé (NULLS LAST si besoin).
- Une ligne par joueur (valeur actuelle, contrat, pied, taille, nationalité, sélections, valeur maximale) :
  utilise gold.dim_player seule, sans la joindre à fact_player_season (sinon un joueur apparaît une fois par saison).
  Pour afficher aussi son club actuel, joins fact_player_season AVEC f.season = '{derniere}'.
- Âge d'un joueur pendant une saison : f.age (pas l'année de naissance).
- Valeur à la fin de chaque saison : f.valeur_fin_saison_eur dans gold.fact_player_season (une ligne par saison) ;
  gold.fact_valuation ne sert que pour l'historique détaillé daté.
- Postes : défenseur central = p.tm_sub_position = 'Centre-Back' ; attaquant = p.tm_position = 'Attack' ;
  milieu = 'Midfield' ; défenseur = 'Defender' ; gardien = 'Goalkeeper' (colonnes tm_position / tm_sub_position de gold.dim_player).
- Question au singulier (« quel joueur », « quel championnat » le plus...) : limit 1. « Combien » : count(*) ou sum().
- Contrat qui se termine en AAAA : extract(year from p.tm_contract_end) = AAAA.
- Joueurs ayant joué pour plusieurs clubs une saison : f.n_clubs >= 2 sur gold.fact_player_season (compter les lignes).
- Écart entre valeur actuelle et valeur maximale : p.tm_peak_value_eur - p.tm_value_eur (gold.dim_player).
- Joueurs sous-cotés selon le modèle : ml.valeur_predite, saison '{derniere}', triés par ecart_pct décroissant
  (ecart_pct positif = valeur prédite supérieure à la valeur Transfermarkt).
- Avec round(), convertis TOUJOURS en numeric d'abord : round((expression)::numeric, 1).
- Réponds uniquement par la requête SQL, sans explication, dans un bloc ```sql.
"""

EXEMPLES = [
    ("Quels sont les 5 milieux de Ligue 1 les plus jeunes cette saison avec au moins 1000 minutes ?",
     """select p.player, f.team, f.age, f.playing_time_min
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '{derniere}' and f.league = 'FRA-Ligue 1' and p.tm_position = 'Midfield'
  and f.playing_time_min >= 1000
order by f.age asc
limit 5;"""),
    ("Quels sont les 3 défenseurs gauchers les plus chers actuellement ?",
     """select p.player, f.team, p.tm_value_eur
from gold.dim_player p
join gold.fact_player_season f on f.player_key = p.player_key and f.season = '{derniere}'
where p.tm_position = 'Defender' and p.tm_foot = 'left'
order by p.tm_value_eur desc nulls last
limit 3;"""),
    ("Quel joueur a le plus gros écart entre sa valeur prédite et sa valeur réelle cette saison ?",
     """select player, team, valeur_reelle_eur, valeur_predite_eur, round(ecart_pct::numeric, 0) as ecart_pct
from ml.valeur_predite
where season = '{derniere}'
order by ecart_pct desc nulls last
limit 1;"""),
    ("Combien de buts Achraf Hakimi a-t-il marqués à chaque saison ?",
     """select f.saison_label, f.team, f.performance_gls
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where p.player_clean ilike '%achraf hakimi%'
order by f.season;"""),
    ("Valeur moyenne des joueurs par championnat cette saison, en millions",
     """select f.league, round(avg(f.valeur_fin_saison_eur) / 1e6::numeric, 1) as valeur_moyenne_meur,
       count(*) as nb_joueurs
from gold.fact_player_season f
where f.season = '{derniere}' and f.valeur_fin_saison_eur is not null
group by f.league
order by valeur_moyenne_meur desc;"""),
]


def _valeurs(engine):
    """Saisons, championnats et postes présents dans la base."""
    with engine.connect() as cx:
        saisons = [r[0] for r in cx.execute(text("select season from gold.dim_season order by season"))]
        ligues = [r[0] for r in cx.execute(text("select league from gold.dim_league order by league"))]
        postes = [r[0] for r in cx.execute(text(
            "select distinct tm_sub_position from gold.dim_player "
            "where tm_sub_position is not null order by 1"))]
    return saisons, ligues, postes


def contexte(db_url):
    """Texte complet (schéma + règles) et dictionnaire des valeurs utiles."""
    saisons, ligues, postes = _valeurs(create_engine(db_url))
    derniere = max(saisons)
    sch = SCHEMA.format(
        saisons=", ".join(f"'{s}'" for s in saisons) + f" ('{derniere}' = la plus récente)",
        ligues=", ".join(f"'{x}'" for x in ligues),
        postes=", ".join(f"'{x}'" for x in postes))
    return sch + "\n" + REGLES.format(derniere=derniere), {"derniere": derniere, "saisons": saisons,
                                                           "ligues": ligues}

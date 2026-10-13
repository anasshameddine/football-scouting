"""
20 questions de test pour l'agent texte vers SQL, chacune avec une requête de référence écrite à la main.
« {derniere} » est remplacé par la saison la plus récente de la base.
ordonne=True : l'ordre des lignes compte (classements).
Les références ne gardent que les colonnes essentielles : le club ou la saison en plus sont tolérés.
"""

QUESTIONS = [
    {"id": 1, "question": "Combien de joueurs marocains y a-t-il dans la base ?", "ordonne": False,
     "sql": "select count(*) from gold.dim_player where is_moroccan"},
    {"id": 2, "question": "Quels sont les 10 meilleurs buteurs cette saison ?", "ordonne": True,
     "sql": """select p.player, f.performance_gls from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' order by f.performance_gls desc nulls last limit 10"""},
    {"id": 3, "question": "Quels sont les 5 joueurs avec la plus grosse valeur Transfermarkt actuelle ?",
     "ordonne": True,
     "sql": "select player, tm_value_eur from gold.dim_player order by tm_value_eur desc nulls last limit 5"},
    {"id": 4, "question": "Combien de joueurs compte chaque championnat cette saison ?", "ordonne": False,
     "sql": """select league, count(*) from gold.fact_player_season where season = '{derniere}'
               group by league"""},
    {"id": 5, "question": "Quel joueur marocain a fait le plus de passes décisives cette saison ?",
     "ordonne": True,
     "sql": """select p.player, f.performance_ast from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and p.is_moroccan
               order by f.performance_ast desc nulls last limit 1"""},
    {"id": 6, "question": "Top 10 des xG par 90 minutes cette saison (au moins 900 minutes jouées)",
     "ordonne": True,
     "sql": """select p.player, f.us_xg_p90 from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and f.playing_time_min >= 900 and f.us_xg_p90 is not null
               order by f.us_xg_p90 desc limit 10"""},
    {"id": 7, "question": "Quel est l'âge moyen des joueurs dans chaque championnat cette saison ?",
     "ordonne": False,
     "sql": """select league, avg(age) from gold.fact_player_season where season = '{derniere}'
               group by league"""},
    {"id": 8, "question": "Quelle est la valeur Transfermarkt actuelle d'Achraf Hakimi ?", "ordonne": False,
     "sql": "select tm_value_eur from gold.dim_player where player_clean = 'achraf hakimi'"},
    {"id": 9, "question": "Quels sont les 10 joueurs les plus sous-cotés selon le modèle cette saison ?",
     "ordonne": True,
     "sql": """select player, ecart_pct from ml.valeur_predite where season = '{derniere}'
               order by ecart_pct desc nulls last limit 10"""},
    {"id": 10, "question": "Combien de joueurs sont gauchers ?", "ordonne": False,
     "sql": "select count(*) from gold.dim_player where tm_foot = 'left'"},
    {"id": 11, "question": "Combien de buts ont été marqués dans chaque championnat cette saison ?",
     "ordonne": False,
     "sql": """select league, sum(performance_gls) from gold.fact_player_season
               where season = '{derniere}' group by league"""},
    {"id": 12, "question": "Quels joueurs de moins de 21 ans ont marqué au moins 5 buts cette saison ?",
     "ordonne": False,
     "sql": """select p.player from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and f.age < 21 and f.performance_gls >= 5"""},
    {"id": 13, "question": "Comment a évolué la valeur de Kylian Mbappé à la fin de chaque saison ?",
     "ordonne": True,
     "sql": """select f.valeur_fin_saison_eur from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where p.player_clean = 'kylian mbappe' order by f.season"""},
    {"id": 14, "question": "Combien de joueurs ont un contrat qui se termine en 2026 ?", "ordonne": False,
     "sql": "select count(*) from gold.dim_player where extract(year from tm_contract_end) = 2026"},
    {"id": 15, "question": "Quels sont les 5 défenseurs centraux avec le plus d'interceptions par 90 minutes "
                           "cette saison (au moins 900 minutes) ?", "ordonne": True,
     "sql": """select p.player, f.performance_int_p90 from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and f.playing_time_min >= 900
                 and p.tm_sub_position = 'Centre-Back'
               order by f.performance_int_p90 desc nulls last limit 5"""},
    {"id": 16, "question": "Quelle est la valeur moyenne des joueurs marocains à la fin de cette saison ?",
     "ordonne": False,
     "sql": """select avg(f.valeur_fin_saison_eur) from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and p.is_moroccan"""},
    {"id": 17, "question": "Quels sont les 5 joueurs dont la valeur actuelle est la plus loin de leur "
                           "valeur maximale en carrière ?", "ordonne": True,
     "sql": """select player, tm_peak_value_eur - tm_value_eur as ecart from gold.dim_player
               where tm_peak_value_eur is not null and tm_value_eur is not null
               order by ecart desc limit 5"""},
    {"id": 18, "question": "Combien de joueurs ont joué pour au moins deux clubs cette saison ?",
     "ordonne": False,
     "sql": "select count(*) from gold.fact_player_season where season = '{derniere}' and n_clubs >= 2"},
    {"id": 19, "question": "Quel championnat compte le plus de cartons rouges cette saison ?", "ordonne": True,
     "sql": """select league, sum(performance_crdr) as rouges from gold.fact_player_season
               where season = '{derniere}' group by league order by rouges desc limit 1"""},
    {"id": 20, "question": "Quels sont les 3 attaquants marocains les plus chers actuellement ?",
     "ordonne": True,
     "sql": """select player, tm_value_eur from gold.dim_player
               where is_moroccan and tm_position = 'Attack'
               order by tm_value_eur desc nulls last limit 3"""},
]


# 10 questions écrites APRÈS la mise au point des règles du prompt sur les 20 premières :
# elles mesurent honnêtement la généralisation (le prompt n'a jamais été ajusté sur elles).
QUESTIONS_NOUVELLES = [
    {"id": 21, "question": "Combien de joueurs ont plus de 30 ans cette saison ?", "ordonne": False,
     "sql": "select count(*) from gold.fact_player_season where season = '{derniere}' and age > 30"},
    {"id": 22, "question": "Quels sont les 3 meilleurs passeurs décisifs de Premier League cette saison ?",
     "ordonne": True,
     "sql": """select p.player, f.performance_ast from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and f.league = 'ENG-Premier League'
               order by f.performance_ast desc nulls last limit 3"""},
    {"id": 23, "question": "Quelle est la taille moyenne des gardiens ?", "ordonne": False,
     "sql": "select avg(tm_height_cm) from gold.dim_player where tm_position = 'Goalkeeper'"},
    {"id": 24, "question": "Combien de joueurs marocains jouent en Liga cette saison ?", "ordonne": False,
     "sql": """select count(*) from gold.fact_player_season f join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and p.is_moroccan and f.league = 'ESP-La Liga'"""},
    {"id": 25, "question": "Quel club a le plus de joueurs dans la base cette saison ?", "ordonne": True,
     "sql": """select team, count(*) as n from gold.fact_player_season where season = '{derniere}'
               group by team order by n desc limit 1"""},
    {"id": 26, "question": "Quels sont les 5 joueurs avec le plus de tirs cadrés par 90 minutes cette saison "
                           "(au moins 900 minutes) ?", "ordonne": True,
     "sql": """select p.player, f.standard_sot_p90 from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and f.playing_time_min >= 900
               order by f.standard_sot_p90 desc nulls last limit 5"""},
    {"id": 27, "question": "Quelle est la valeur totale des joueurs de chaque championnat à la fin de cette saison ?",
     "ordonne": False,
     "sql": """select league, sum(valeur_fin_saison_eur) from gold.fact_player_season
               where season = '{derniere}' group by league"""},
    {"id": 28, "question": "Combien de joueurs ont au moins 50 sélections internationales ?", "ordonne": False,
     "sql": "select count(*) from gold.dim_player where tm_intl_caps >= 50"},
    {"id": 29, "question": "Quel joueur marocain a joué le plus de minutes cette saison ?", "ordonne": True,
     "sql": """select p.player, f.playing_time_min from gold.fact_player_season f
               join gold.dim_player p on p.player_key = f.player_key
               where f.season = '{derniere}' and p.is_moroccan
               order by f.playing_time_min desc nulls last limit 1"""},
    {"id": 30, "question": "Quelle valeur le modèle prédit-il pour Brahim Díaz cette saison ?", "ordonne": False,
     "sql": """select valeur_predite_eur from ml.valeur_predite
               where season = '{derniere}' and player = 'Brahim Díaz'"""},
]

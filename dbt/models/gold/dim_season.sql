select distinct season, saison_label, annee_debut,
       make_date(annee_debut + 1, 6, 30) as fin_saison
from {{ ref('stg_fbref_player_team_season') }}

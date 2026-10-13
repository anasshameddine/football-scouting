-- Un joueur ne doit apparaître qu'une fois par saison.
select player_key, season, count(*) as n
from {{ ref('fact_player_season') }}
group by 1, 2 having count(*) > 1

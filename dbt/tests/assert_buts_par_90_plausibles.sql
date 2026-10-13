-- Plus de 3 buts par 90 minutes sur 450 minutes ou plus : erreur de données probable.
select player_key, season, performance_gls_p90
from {{ ref('fact_player_season') }}
where playing_time_min >= 450 and performance_gls_p90 > 3

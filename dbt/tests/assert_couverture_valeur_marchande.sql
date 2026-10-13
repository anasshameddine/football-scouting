{{ config(severity='warn') }}
-- Au moins 90 % des joueurs retenus doivent avoir une valeur Transfermarkt.
select round(100.0 * count(tm_value_eur) / count(*), 1) as pct_avec_valeur
from {{ ref('mart_scouting') }}
having 100.0 * count(tm_value_eur) / count(*) < 90

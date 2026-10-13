{{ config(severity='warn') }}
-- Au moins 95 % des joueurs des 5 grands championnats doivent avoir des données Understat.
select round(100.0 * count(us_xg) / count(*), 1) as pct_avec_xg
from {{ ref('mart_scouting') }}
where league in ('ENG-Premier League','ESP-La Liga','ITA-Serie A','GER-Bundesliga','FRA-Ligue 1')
having 100.0 * count(us_xg) / count(*) < 95

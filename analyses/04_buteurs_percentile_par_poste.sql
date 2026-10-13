-- Question : parmi les attaquants, qui marque le plus (hors penalty) par 90 minutes, et à quel percentile ?
-- Technique : PERCENT_RANK() et NTILE() sur un échantillon filtré (au moins 900 minutes).
with attaquants as (
    select p.player, f.team, f.league, f.age, f.playing_time_min,
           f.performance_g_minus_pk_p90 as buts_p90,
           f.valeur_fin_saison_eur as valeur_eur
    from gold.fact_player_season f
    join gold.dim_player p using (player_key)
    where f.season = '2526' and p.tm_sub_position in ('Centre-Forward', 'Second Striker')
      and f.playing_time_min >= 900
),
classes as (
    select *, percent_rank() over (order by buts_p90) as percentile,
              ntile(4) over (order by buts_p90 desc) as quartile
    from attaquants
)
select player as joueur, team as club, league as championnat, age,
       round(buts_p90::numeric, 2) as buts_p90,
       round((100 * percentile)::numeric) as percentile,
       quartile,
       round((valeur_eur / 1e6)::numeric, 1) as valeur_meur
from classes
order by buts_p90 desc
limit 20;

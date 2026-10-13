-- Question : quels joueurs sont les plus réguliers (4 saisons d'affilée à plus de 1500 minutes) et lesquels progressent ?
-- Technique : CTE, HAVING, écart-type (STDDEV), régression linéaire (REGR_SLOPE) sur la valeur au fil des saisons.
with saisons as (
    select player_key, left(season, 2)::int as saison_num, playing_time_min as minutes,
           performance_g_minus_pk_p90 as buts_p90, valeur_fin_saison_eur as valeur_eur, team
    from gold.fact_player_season
    where playing_time_min >= 1500 and valeur_fin_saison_eur is not null
)
select p.player as joueur, max(s.team) filter (where s.saison_num = 25) as club_actuel,
       count(*) as saisons_jouees,
       round(avg(s.minutes)) as minutes_moyennes,
       round(stddev(s.buts_p90)::numeric, 2) as variabilite_buts_p90,
       round((regr_slope(s.valeur_eur, s.saison_num) / 1e6)::numeric, 1) as gain_meur_par_saison,
       round((max(s.valeur_eur) filter (where s.saison_num = 25) / 1e6)::numeric, 1) as valeur_actuelle_meur
from saisons s
join gold.dim_player p using (player_key)
group by p.player, p.player_key
having count(*) >= 4 and max(s.saison_num) = 25
order by gain_meur_par_saison desc nulls last
limit 15;

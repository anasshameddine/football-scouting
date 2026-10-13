-- Question : comment évolue la valeur médiane des joueurs de chaque championnat, et quelle est la tendance ?
-- Technique : percentile_cont (médiane), LAG() pour la variation, moyenne glissante par fenêtre (ROWS BETWEEN).
with par_saison as (
    select f.league, f.season, f.saison_label,
           percentile_cont(0.5) within group (order by f.valeur_fin_saison_eur) as mediane_eur,
           count(*) as nb_joueurs
    from gold.fact_player_season f
    where f.valeur_fin_saison_eur is not null and f.playing_time_min >= 900
    group by f.league, f.season, f.saison_label
)
select league as championnat, saison_label as saison, nb_joueurs,
       round((mediane_eur / 1e6)::numeric, 2) as mediane_meur,
       round((100.0 * (mediane_eur / lag(mediane_eur) over (partition by league order by season) - 1))::numeric) as variation_pct,
       round(((avg(mediane_eur) over (partition by league order by season
                                     rows between 1 preceding and current row)) / 1e6)::numeric, 2) as moyenne_2_saisons_meur
from par_saison
where league in ('ENG-Premier League', 'ITA-Serie A', 'FRA-Ligue 1', 'POR-Primeira Liga', 'KSA-Pro League')
order by league, season;

-- Question : quels sont les 3 joueurs les plus chers de chaque championnat en 2025-26 ?
-- Technique : ROW_NUMBER() sur une partition (un classement par championnat), CTE.
with joueurs as (
    select f.league, p.player, f.team, f.age, p.tm_sub_position as poste,
           f.valeur_fin_saison_eur as valeur_eur,
           row_number() over (partition by f.league
                              order by f.valeur_fin_saison_eur desc nulls last) as rang
    from gold.fact_player_season f
    join gold.dim_player p using (player_key)
    where f.season = '2526' and f.valeur_fin_saison_eur is not null
)
select league as championnat, rang, player as joueur, team as club, age, poste,
       round((valeur_eur / 1e6)::numeric, 1) as valeur_meur
from joueurs
where rang <= 3
order by league, rang;

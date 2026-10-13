-- Question : à quel âge un joueur vaut-il le plus, selon son poste ?
-- Technique : percentile_cont (médiane), HAVING pour écarter les âges trop rares, FILTER.
select case when p.tm_sub_position in ('Centre-Back') then 'Défenseur central'
            when p.tm_sub_position in ('Left-Back', 'Right-Back') then 'Latéral'
            when p.tm_sub_position in ('Defensive Midfield', 'Central Midfield', 'Attacking Midfield') then 'Milieu'
            when p.tm_sub_position in ('Left Winger', 'Right Winger', 'Left Midfield', 'Right Midfield') then 'Ailier'
            else 'Attaquant' end as poste,
       f.age::int as age,
       count(*) as nb_joueurs,
       round((percentile_cont(0.5) within group (order by f.valeur_fin_saison_eur) / 1e6)::numeric, 2) as valeur_mediane_meur,
       round((percentile_cont(0.9) within group (order by f.valeur_fin_saison_eur) / 1e6)::numeric, 2) as valeur_p90_meur
from gold.fact_player_season f
join gold.dim_player p using (player_key)
where f.season = '2526' and f.valeur_fin_saison_eur is not null and f.playing_time_min >= 900
  and p.tm_sub_position is not null and p.tm_sub_position <> 'Goalkeeper'
  and f.age between 18 and 34
group by 1, 2
having count(*) >= 15
order by 1, 2;

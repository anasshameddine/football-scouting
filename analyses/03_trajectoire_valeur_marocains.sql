-- Question : comment la valeur des joueurs marocains les plus chers a-t-elle évolué saison après saison ?
-- Technique : agrégation conditionnelle (pivot) et classement par la valeur la plus récente.
select p.player as joueur,
       round((max(f.valeur_fin_saison_eur) filter (where f.season = '2122') / 1e6)::numeric, 1) as v_2122,
       round((max(f.valeur_fin_saison_eur) filter (where f.season = '2223') / 1e6)::numeric, 1) as v_2223,
       round((max(f.valeur_fin_saison_eur) filter (where f.season = '2324') / 1e6)::numeric, 1) as v_2324,
       round((max(f.valeur_fin_saison_eur) filter (where f.season = '2425') / 1e6)::numeric, 1) as v_2425,
       round((max(f.valeur_fin_saison_eur) filter (where f.season = '2526') / 1e6)::numeric, 1) as v_2526,
       rank() over (order by max(f.valeur_fin_saison_eur) filter (where f.season = '2526') desc nulls last) as rang_actuel
from gold.fact_player_season f
join gold.dim_player p using (player_key)
where p.is_moroccan
group by p.player, p.player_key
having max(f.valeur_fin_saison_eur) filter (where f.season = '2526') is not null
order by rang_actuel
limit 15;

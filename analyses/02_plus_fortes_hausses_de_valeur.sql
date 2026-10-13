-- Question : quels joueurs ont le plus pris de valeur entre 2024-25 et 2025-26 ?
-- Technique : LAG() pour comparer une saison à la précédente du même joueur.
with historique as (
    select player_key, season, team, age, valeur_fin_saison_eur as valeur_eur,
           lag(valeur_fin_saison_eur) over (partition by player_key order by season) as valeur_precedente
    from gold.fact_player_season
    where valeur_fin_saison_eur is not null
)
select p.player as joueur, h.team as club, h.age,
       round((h.valeur_precedente / 1e6)::numeric, 1) as valeur_2425_meur,
       round((h.valeur_eur / 1e6)::numeric, 1)        as valeur_2526_meur,
       round(((h.valeur_eur - h.valeur_precedente) / 1e6)::numeric, 1) as gain_meur,
       round(100.0 * (h.valeur_eur::numeric / h.valeur_precedente - 1)) as gain_pct
from historique h
join gold.dim_player p using (player_key)
where h.season = '2526' and h.valeur_precedente >= 1e6
order by h.valeur_eur - h.valeur_precedente desc
limit 15;

-- Question : quels clubs dépendent le plus d'un seul joueur (part du plus cher dans la valeur de l'effectif) ?
-- Technique : CTE, SUM() OVER (partition) pour le total du club, ROW_NUMBER() pour isoler le joueur vedette.
with effectif as (
    select f.league, f.team, p.player, f.valeur_fin_saison_eur as valeur_eur,
           sum(f.valeur_fin_saison_eur) over (partition by f.league, f.team) as valeur_club,
           count(*)                       over (partition by f.league, f.team) as nb_joueurs,
           row_number() over (partition by f.league, f.team
                              order by f.valeur_fin_saison_eur desc) as rang_club
    from gold.fact_player_season f
    join gold.dim_player p using (player_key)
    where f.season = '2526' and f.valeur_fin_saison_eur is not null
)
select league as championnat, team as club, player as joueur_vedette,
       round((valeur_eur / 1e6)::numeric, 1)  as valeur_vedette_meur,
       round((valeur_club / 1e6)::numeric, 1) as valeur_effectif_meur,
       round(100.0 * valeur_eur::numeric / valeur_club) as part_vedette_pct,
       nb_joueurs
from effectif
where rang_club = 1 and nb_joueurs >= 10 and valeur_club >= 20e6
order by part_vedette_pct desc
limit 15;

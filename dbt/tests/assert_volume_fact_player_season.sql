-- Contrôle de volume : la table doit garder au moins 5 000 lignes.
select count(*) as n from {{ ref('fact_player_season') }} having count(*) < 5000

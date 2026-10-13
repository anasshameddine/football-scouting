-- Contrôle de volume : au moins 3 000 joueurs et 50 Marocains dans la table du dashboard.
select n, n_maroc from (
  select count(*) as n, count(*) filter (where is_moroccan) as n_maroc
  from {{ ref('mart_scouting') }}) t
where n < 3000 or n_maroc < 50

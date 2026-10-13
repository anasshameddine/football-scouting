-- Aucun joueur ne peut avoir des minutes négatives ou plus de 6 000 sur une saison.
select * from {{ ref('fact_player_season') }}
where playing_time_min < 0 or playing_time_min > 6000

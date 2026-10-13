-- Understat rattaché aux lignes FBref grâce aux tables de rapprochement (nom exact ou proche).
select
    pu.league, pu.season, pu.team, pu.player,
    u.minutes::numeric     as us_minutes,
    u.xg                   as us_xg,
    u.np_xg                as us_np_xg,
    u.xa                   as us_xa,
    u.shots                as us_shots,
    u.key_passes           as us_key_passes,
    u.xg_chain             as us_xg_chain,
    u.xg_buildup           as us_xg_buildup,
    pu.methode             as us_match
from {{ source('mapping', 'player_understat') }} pu
join {{ source('mapping', 'team_understat') }} tu
  on tu.league = pu.league and tu.season = pu.season and tu.team = pu.team
join {{ source('raw', 'understat_player_season') }} u
  on u.league = pu.league and u.season::text = pu.season
 and u.team = tu.team_us and u.player = pu.player_us

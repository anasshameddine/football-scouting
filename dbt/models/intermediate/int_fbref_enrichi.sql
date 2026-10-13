-- Ligne FBref (joueur, club, saison) + identifiant Transfermarkt + Understat.
-- player_key : identifiant stable d'un joueur, partagé entre saisons et graphies de nom.
select
    f.*,
    pt.tm_player_id,
    pt.methode                                          as tm_match,
    coalesce('tm:' || pt.tm_player_id::text,
             'fb:' || f.player_clean || '|' || coalesce(f.born::text, '?')) as player_key,
    u.us_minutes, u.us_xg, u.us_np_xg, u.us_xa, u.us_shots,
    u.us_key_passes, u.us_xg_chain, u.us_xg_buildup
from {{ ref('stg_fbref_player_team_season') }} f
left join {{ source('mapping', 'player_transfermarkt') }} pt
       on pt.player = f.player and pt.born = f.born
      and (pt.league is null or pt.league = f.league)
left join {{ ref('stg_understat') }} u
       on u.league = f.league and u.season = f.season and u.team = f.team and u.player = f.player

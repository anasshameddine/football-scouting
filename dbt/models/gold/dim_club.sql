select md5(league || '|' || team) as club_key, team as club, league
from (select distinct league, team from {{ ref('stg_fbref_player_team_season') }}) c

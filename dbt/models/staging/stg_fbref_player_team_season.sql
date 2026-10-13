-- Une ligne par joueur, club, championnat et saison : les 4 tables FBref réunies, typées et dédoublonnées.
with std as (select distinct on (league, season, team, player) * from {{ source('raw', 'fbref_standard') }}
             order by league, season, team, player),
     sho as (select distinct on (league, season, team, player) * from {{ source('raw', 'fbref_shooting') }}
             order by league, season, team, player),
     mis as (select distinct on (league, season, team, player) * from {{ source('raw', 'fbref_misc') }}
             order by league, season, team, player),
     pt  as (select distinct on (league, season, team, player) * from {{ source('raw', 'fbref_playing_time') }}
             order by league, season, team, player)
select
    std.league,
    std.season::text                                              as season,
    2000 + substr(lpad(std.season::text, 4, '0'), 1, 2)::int      as annee_debut,
    '20' || substr(lpad(std.season::text, 4, '0'), 1, 2) || '-20'
         || substr(lpad(std.season::text, 4, '0'), 3, 2)          as saison_label,
    std.team,
    std.player,
    lower(trim(unaccent(std.player)))                             as player_clean,
    (regexp_split_to_array(trim(std.nation), '\s+'))[cardinality(regexp_split_to_array(trim(std.nation), '\s+'))] as nation_code,
    split_part(std.pos, ',', 1)                                   as pos_main,
    std.pos,
    {{ num('std.age') }}                                          as age,
    {{ num('std.born') }}                                         as born,
    {{ num('coalesce(pt.playing_time_min::text, std.playing_time_min::text)') }} as minutes,
    {{ num('coalesce(pt.playing_time_mp::text, std.playing_time_mp::text)') }}   as matches,
    {{ num('coalesce(pt.starts_starts::text, std.playing_time_starts::text)') }} as starts,
    {{ num('std.performance_gls') }}        as performance_gls,
    {{ num('std.performance_ast') }}        as performance_ast,
    {{ num('std.performance_g_minus_pk') }} as performance_g_minus_pk,
    {{ num('std.performance_pk') }}         as performance_pk,
    {{ num('std.performance_pkatt') }}      as performance_pkatt,
    {{ num('std.performance_crdy') }}       as performance_crdy,
    {{ num('std.performance_crdr') }}       as performance_crdr,
    {{ num('mis.performance_2crdy') }}      as performance_2crdy,
    {{ num('mis.performance_fls') }}        as performance_fls,
    {{ num('mis.performance_fld') }}        as performance_fld,
    {{ num('mis.performance_off') }}        as performance_off,
    {{ num('mis.performance_crs') }}        as performance_crs,
    {{ num('mis.performance_int') }}        as performance_int,
    {{ num('mis.performance_tklw') }}       as performance_tklw,
    {{ num('mis.performance_pkwon') }}      as performance_pkwon,
    {{ num('mis.performance_pkcon') }}      as performance_pkcon,
    {{ num('mis.performance_og') }}         as performance_og,
    {{ num('sho.standard_sh') }}            as standard_sh,
    {{ num('sho.standard_sot') }}           as standard_sot
from std
left join sho using (league, season, team, player)
left join mis using (league, season, team, player)
left join pt  using (league, season, team, player)
where std.league not in ({{ "'" + var('exclure_ligues') | join("','") + "'" }})

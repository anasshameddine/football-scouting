-- Faits : une ligne par joueur et saison, avec stats par 90 minutes et valeur marchande
-- à la fin de la saison (dernière valeur Transfermarkt connue au 30 juin).
with valeur_fin as (
    select distinct on (j.player_key, j.season)
           j.player_key, j.season, v.valeur_eur, v.date_valeur
    from {{ ref('int_joueur_saison') }} j
    join {{ ref('stg_tm_valuations') }} v
      on v.tm_player_id = j.tm_player_id
     and v.date_valeur <= make_date(j.annee_debut + 1, 6, 30)
    order by j.player_key, j.season, v.date_valeur desc
)
select
    j.player_key,
    j.season,
    j.saison_label,
    md5(j.league || '|' || j.team)  as club_key,
    j.team, j.league, j.teams_all, j.n_clubs,
    j.age, j.pos, j.pos_main,
    j.minutes   as playing_time_min,
    j.matches   as playing_time_mp,
    j.starts    as playing_time_starts,
    j.us_minutes,
    j.performance_gls, j.performance_gls / nullif(j.minutes / 90.0, 0) as performance_gls_p90,
    j.performance_ast, j.performance_ast / nullif(j.minutes / 90.0, 0) as performance_ast_p90,
    j.performance_g_minus_pk, j.performance_g_minus_pk / nullif(j.minutes / 90.0, 0) as performance_g_minus_pk_p90,
    j.performance_pk, j.performance_pk / nullif(j.minutes / 90.0, 0) as performance_pk_p90,
    j.performance_pkatt, j.performance_pkatt / nullif(j.minutes / 90.0, 0) as performance_pkatt_p90,
    j.performance_crdy, j.performance_crdy / nullif(j.minutes / 90.0, 0) as performance_crdy_p90,
    j.performance_crdr, j.performance_crdr / nullif(j.minutes / 90.0, 0) as performance_crdr_p90,
    j.performance_2crdy, j.performance_2crdy / nullif(j.minutes / 90.0, 0) as performance_2crdy_p90,
    j.performance_fls, j.performance_fls / nullif(j.minutes / 90.0, 0) as performance_fls_p90,
    j.performance_fld, j.performance_fld / nullif(j.minutes / 90.0, 0) as performance_fld_p90,
    j.performance_off, j.performance_off / nullif(j.minutes / 90.0, 0) as performance_off_p90,
    j.performance_crs, j.performance_crs / nullif(j.minutes / 90.0, 0) as performance_crs_p90,
    j.performance_int, j.performance_int / nullif(j.minutes / 90.0, 0) as performance_int_p90,
    j.performance_tklw, j.performance_tklw / nullif(j.minutes / 90.0, 0) as performance_tklw_p90,
    j.performance_pkwon, j.performance_pkwon / nullif(j.minutes / 90.0, 0) as performance_pkwon_p90,
    j.performance_pkcon, j.performance_pkcon / nullif(j.minutes / 90.0, 0) as performance_pkcon_p90,
    j.performance_og, j.performance_og / nullif(j.minutes / 90.0, 0) as performance_og_p90,
    j.standard_sh, j.standard_sh / nullif(j.minutes / 90.0, 0) as standard_sh_p90,
    j.standard_sot, j.standard_sot / nullif(j.minutes / 90.0, 0) as standard_sot_p90,
    j.us_xg, j.us_xg / nullif(j.us_minutes / 90.0, 0) as us_xg_p90,
    j.us_np_xg, j.us_np_xg / nullif(j.us_minutes / 90.0, 0) as us_np_xg_p90,
    j.us_xa, j.us_xa / nullif(j.us_minutes / 90.0, 0) as us_xa_p90,
    j.us_shots, j.us_shots / nullif(j.us_minutes / 90.0, 0) as us_shots_p90,
    j.us_key_passes, j.us_key_passes / nullif(j.us_minutes / 90.0, 0) as us_key_passes_p90,
    j.us_xg_chain, j.us_xg_chain / nullif(j.us_minutes / 90.0, 0) as us_xg_chain_p90,
    j.us_xg_buildup, j.us_xg_buildup / nullif(j.us_minutes / 90.0, 0) as us_xg_buildup_p90,
    j.a_understat,
    vf.valeur_eur       as valeur_fin_saison_eur,
    vf.date_valeur      as date_valeur_fin_saison
from {{ ref('int_joueur_saison') }} j
left join valeur_fin vf using (player_key, season)

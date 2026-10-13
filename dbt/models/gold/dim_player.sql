-- Une ligne par joueur : identité FBref (saison la plus récente) + profil Transfermarkt.
with dernier as (
    select distinct on (player_key)
           player_key, player, player_clean, born, nation_code, tm_player_id, tm_match
    from {{ ref('int_joueur_saison') }}
    order by player_key, annee_debut desc
),
maroc as (
    select player_key, bool_or(is_moroccan_fbref) as is_moroccan_fbref
    from {{ ref('int_joueur_saison') }} group by player_key
)
select
    d.player_key, d.player, d.player_clean, d.born, d.nation_code,
    d.tm_player_id, d.tm_match,
    t.tm_sub_position, t.tm_position, t.tm_foot, t.tm_height_cm, t.tm_contract_end,
    t.tm_citizenship, t.tm_intl_caps, t.tm_national_team_id, t.tm_competition,
    t.tm_value_eur, t.tm_peak_value_eur,
    m.is_moroccan_fbref,
    coalesce(m.is_moroccan_fbref, false)
       or coalesce(t.tm_citizenship = 'Morocco', false)
       or coalesce(t.tm_national_team_id = {{ var('maroc_tm_id') }}, false) as is_moroccan
from dernier d
join maroc m using (player_key)
left join {{ ref('stg_tm_players') }} t on t.tm_player_id = d.tm_player_id

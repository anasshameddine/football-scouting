select
    player_id                              as tm_player_id,
    name                                   as tm_name,
    date_of_birth::date                    as date_naissance,
    extract(year from date_of_birth::date)::int as born,
    position                               as tm_position,
    sub_position                           as tm_sub_position,
    foot                                   as tm_foot,
    height_in_cm                           as tm_height_cm,
    contract_expiration_date::date         as tm_contract_end,
    country_of_citizenship                 as tm_citizenship,
    international_caps                     as tm_intl_caps,
    current_national_team_id               as tm_national_team_id,
    current_club_domestic_competition_id   as tm_competition,
    current_club_id                        as tm_club_id,
    market_value_in_eur                    as tm_value_eur,
    highest_market_value_in_eur            as tm_peak_value_eur,
    last_season
from {{ source('raw', 'tm_players') }}

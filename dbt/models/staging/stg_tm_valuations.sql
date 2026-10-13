select player_id as tm_player_id, date::date as date_valeur, market_value_in_eur as valeur_eur
from {{ source('raw', 'tm_player_valuations') }}
where market_value_in_eur is not null

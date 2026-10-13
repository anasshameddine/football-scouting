-- Historique des valeurs marchandes, limité aux joueurs de la base.
select p.player_key, v.tm_player_id, v.date_valeur, v.valeur_eur
from {{ ref('stg_tm_valuations') }} v
join {{ ref('dim_player') }} p on p.tm_player_id = v.tm_player_id

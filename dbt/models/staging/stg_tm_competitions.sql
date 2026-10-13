select competition_id as tm_competition, name as competition, country_name as pays, confederation
from {{ source('raw', 'tm_competitions') }}

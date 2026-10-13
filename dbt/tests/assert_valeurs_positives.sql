select * from {{ ref('fact_valuation') }} where valeur_eur < 0
union all
select player_key, null, null, null from {{ ref('fact_player_season') }}
where valeur_fin_saison_eur < 0

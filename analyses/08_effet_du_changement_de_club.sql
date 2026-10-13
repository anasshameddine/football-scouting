-- Question : quand un joueur change de club, sa valeur monte-t-elle ou baisse-t-elle ?
-- Technique : LAG() sur le club et la valeur, CASE pour classer les transferts, agrégation par type.
with parcours as (
    select player_key, season, team, valeur_fin_saison_eur as valeur_eur,
           lag(team)                  over (partition by player_key order by season) as club_precedent,
           lag(valeur_fin_saison_eur) over (partition by player_key order by season) as valeur_precedente
    from gold.fact_player_season
    where playing_time_min >= 900 and valeur_fin_saison_eur is not null
),
saisons_comparables as (
    select *, (club_precedent is not null and club_precedent <> team) as a_change_de_club,
           valeur_eur::numeric / valeur_precedente as ratio
    from parcours
    where valeur_precedente >= 500000
)
select case when a_change_de_club then 'Change de club' else 'Reste dans son club' end as situation,
       count(*) as nb_cas,
       round((percentile_cont(0.5) within group (order by ratio) - 1)::numeric * 100) as variation_mediane_pct,
       round(100.0 * avg((ratio > 1)::int)) as part_en_hausse_pct,
       round(100.0 * avg((ratio < 0.8)::int)) as part_forte_baisse_pct
from saisons_comparables
group by a_change_de_club
order by a_change_de_club;

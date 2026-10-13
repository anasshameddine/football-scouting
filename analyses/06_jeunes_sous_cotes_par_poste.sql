-- Question : parmi les moins de 23 ans, quels joueurs le modèle juge-t-il les plus sous-cotés, poste par poste ?
-- Technique : jointure avec la table des prédictions (schéma ml), DENSE_RANK() par poste.
with candidats as (
    select v.player, v.team, v.league, v.age, v.tm_sub_position as poste,
           v.valeur_reelle_eur, v.valeur_predite_eur,
           v.valeur_predite_eur - v.valeur_reelle_eur as ecart_eur,
           dense_rank() over (partition by v.tm_sub_position
                              order by v.valeur_predite_eur - v.valeur_reelle_eur desc) as rang_poste
    from ml.valeur_predite v
    where v.season = '2526' and v.age < 23 and v.valeur_reelle_eur >= 500000
      and v.playing_time_min >= 900
)
select poste, rang_poste, player as joueur, team as club, league as championnat, age,
       round((valeur_reelle_eur / 1e6)::numeric, 1)  as reelle_meur,
       round((valeur_predite_eur / 1e6)::numeric, 1) as predite_meur
from candidats
where rang_poste <= 2
order by poste, rang_poste;

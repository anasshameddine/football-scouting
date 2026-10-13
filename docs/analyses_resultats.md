# Analyses SQL : résultats

Généré le 2026-10-12 par `analyses/run.py` sur le schéma gold (et ml pour la 06).

## 08_effet_du_changement_de_club

**Question.** quand un joueur change de club, sa valeur monte-t-elle ou baisse-t-elle ?  
**Technique.** LAG() sur le club et la valeur, CASE pour classer les transferts, agrégation par type.

| situation           |   nb_cas |   variation_mediane_pct |   part_en_hausse_pct |   part_forte_baisse_pct |
|:--------------------|---------:|------------------------:|---------------------:|------------------------:|
| Reste dans son club |     6230 |                       0 |                   36 |                      32 |
| Change de club      |     3127 |                     -11 |                   35 |                      40 |

[Requête](08_effet_du_changement_de_club.sql)

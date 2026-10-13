# Assistant : précision de l'agent texte vers SQL

Modèle : `qwen2.5:7b` (Ollama, local). Date : 13/10/2026.

**28 / 30 réponses justes (93%)**, temps médian 11 s par question.

- Questions 1-20 (règles du prompt ajustées sur leurs erreurs) : **18 / 20**
- Questions 21-30 (jamais vues pendant la mise au point) : **10 / 10**

Le score des questions 21-30 est le plus honnête : le prompt n'a pas été corrigé en les regardant.

Une réponse est juste si elle renvoie les mêmes données que la requête de référence (colonnes en plus tolérées, montants en millions acceptés).

| # | Question | Juste | Essais | Temps (s) |
|---|---|---|---|---|
| 1 | Combien de joueurs marocains y a-t-il dans la base ? | oui | 1 | 18.7 |
| 2 | Quels sont les 10 meilleurs buteurs cette saison ? | oui | 1 | 10.9 |
| 3 | Quels sont les 5 joueurs avec la plus grosse valeur Transfermarkt actuelle ? | oui | 1 | 7.8 |
| 4 | Combien de joueurs compte chaque championnat cette saison ? | oui | 1 | 9.0 |
| 5 | Quel joueur marocain a fait le plus de passes décisives cette saison ? | oui | 1 | 11.4 |
| 6 | Top 10 des xG par 90 minutes cette saison (au moins 900 minutes jouées) | oui | 1 | 14.5 |
| 7 | Quel est l'âge moyen des joueurs dans chaque championnat cette saison ? | oui | 1 | 10.3 |
| 8 | Quelle est la valeur Transfermarkt actuelle d'Achraf Hakimi ? | oui | 1 | 7.3 |
| 9 | Quels sont les 10 joueurs les plus sous-cotés selon le modèle cette saison ? | non | 1 | 21.3 |
| 10 | Combien de joueurs sont gauchers ? | oui | 1 | 5.7 |
| 11 | Combien de buts ont été marqués dans chaque championnat cette saison ? | oui | 1 | 9.6 |
| 12 | Quels joueurs de moins de 21 ans ont marqué au moins 5 buts cette saison ? | non | 1 | 12.8 |
| 13 | Comment a évolué la valeur de Kylian Mbappé à la fin de chaque saison ? | oui | 1 | 11.1 |
| 14 | Combien de joueurs ont un contrat qui se termine en 2026 ? | oui | 1 | 7.2 |
| 15 | Quels sont les 5 défenseurs centraux avec le plus d'interceptions par 90 minutes cette saison (au moins 900 minutes) ? | oui | 2 | 25.9 |
| 16 | Quelle est la valeur moyenne des joueurs marocains à la fin de cette saison ? | oui | 1 | 12.1 |
| 17 | Quels sont les 5 joueurs dont la valeur actuelle est la plus loin de leur valeur maximale en carrière ? | oui | 1 | 14.0 |
| 18 | Combien de joueurs ont joué pour au moins deux clubs cette saison ? | oui | 1 | 8.0 |
| 19 | Quel championnat compte le plus de cartons rouges cette saison ? | oui | 1 | 10.6 |
| 20 | Quels sont les 3 attaquants marocains les plus chers actuellement ? | oui | 1 | 13.5 |
| 21 | Combien de joueurs ont plus de 30 ans cette saison ? | oui | 1 | 9.2 |
| 22 | Quels sont les 3 meilleurs passeurs décisifs de Premier League cette saison ? | oui | 1 | 12.4 |
| 23 | Quelle est la taille moyenne des gardiens ? | oui | 1 | 7.2 |
| 24 | Combien de joueurs marocains jouent en Liga cette saison ? | oui | 1 | 11.0 |
| 25 | Quel club a le plus de joueurs dans la base cette saison ? | oui | 1 | 9.7 |
| 26 | Quels sont les 5 joueurs avec le plus de tirs cadrés par 90 minutes cette saison (au moins 900 minutes) ? | oui | 1 | 13.4 |
| 27 | Quelle est la valeur totale des joueurs de chaque championnat à la fin de cette saison ? | oui | 1 | 12.5 |
| 28 | Combien de joueurs ont au moins 50 sélections internationales ? | oui | 1 | 6.9 |
| 29 | Quel joueur marocain a joué le plus de minutes cette saison ? | oui | 1 | 12.5 |
| 30 | Quelle valeur le modèle prédit-il pour Brahim Díaz cette saison ? | oui | 1 | 9.4 |

## Requêtes générées

**1. Combien de joueurs marocains y a-t-il dans la base ?** (juste)

```sql
select count(*) as nb_joueurs
from gold.dim_player p
where p.is_moroccan = true
```

**2. Quels sont les 10 meilleurs buteurs cette saison ?** (juste)

```sql
select p.player, f.team, f.performance_gls
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526'
order by f.performance_gls desc nulls last
limit 10
```

**3. Quels sont les 5 joueurs avec la plus grosse valeur Transfermarkt actuelle ?** (juste)

```sql
select p.player, p.tm_value_eur as valeur_transfermarkt
from gold.dim_player p
order by p.tm_value_eur desc nulls last
limit 5
```

**4. Combien de joueurs compte chaque championnat cette saison ?** (juste)

```sql
select f.league, count(*) as nb_joueurs
from gold.fact_player_season f
where f.season = '2526'
group by f.league
order by nb_joueurs desc
```

**5. Quel joueur marocain a fait le plus de passes décisives cette saison ?** (juste)

```sql
select p.player, f.team, f.performance_ast
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where p.is_moroccan and f.season = '2526'
order by f.performance_ast desc nulls last
limit 1
```

**6. Top 10 des xG par 90 minutes cette saison (au moins 900 minutes jouées)** (juste)

```sql
select p.player, f.team, f.league, f.us_xg_p90
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and f.us_xg_p90 is not null and f.playing_time_min >= 900
order by f.us_xg_p90 desc nulls last
limit 10
```

**7. Quel est l'âge moyen des joueurs dans chaque championnat cette saison ?** (juste)

```sql
select f.league, round(avg(f.age) :: numeric, 1) as age_moyen
from gold.fact_player_season f
where f.season = '2526'
group by f.league
order by age_moyen desc
```

**8. Quelle est la valeur Transfermarkt actuelle d'Achraf Hakimi ?** (juste)

```sql
select p.tm_value_eur as valeur_transfermarkt_eur
from gold.dim_player p
where p.player_clean ilike '%achraf hakimi%'
```

**9. Quels sont les 10 joueurs les plus sous-cotés selon le modèle cette saison ?** (fausse)

```sql
SELECT
  p.player,
  f.team,
  p.tm_value_eur,
  f.valeur_fin_saison_eur,
  ROUND(CAST((
    f.valeur_fin_saison_eur / p.tm_value_eur - 1
  ) * 100 AS DECIMAL), 0) AS ecart_pct
FROM ml.valeur_predite AS v
JOIN gold.fact_player_season AS f
  ON v.player_key = f.player_key AND v.season = f.season
JOIN gold.dim_player AS p
  ON p.player_key = v.player_key
WHERE
  v.season = '2526' AND v.playing_time_min >= 450
ORDER BY
  ecart_pct DESC NULLS LAST
LIMIT 10
```

**10. Combien de joueurs sont gauchers ?** (juste)

```sql
select count(*) as nb_joueurs
from gold.dim_player
where tm_foot = 'left'
```

**11. Combien de buts ont été marqués dans chaque championnat cette saison ?** (juste)

```sql
select f.league, sum(f.performance_gls) as buts_marques
from gold.fact_player_season f
where f.season = '2526'
group by f.league
order by buts_marques desc
```

**12. Quels joueurs de moins de 21 ans ont marqué au moins 5 buts cette saison ?** (fausse)

```sql
select p.player, f.team, f.performance_gls
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and f.performance_gls >= 5 and p.born >= 2005
order by f.performance_gls desc nulls last
```

**13. Comment a évolué la valeur de Kylian Mbappé à la fin de chaque saison ?** (juste)

```sql
select f.saison_label, f.valeur_fin_saison_eur / 1e6 as valeur_fin_saison_meur
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where p.player_clean ilike '%kylian mbappe%'
order by f.season
```

**14. Combien de joueurs ont un contrat qui se termine en 2026 ?** (juste)

```sql
select count(*) as nb_joueurs
from gold.dim_player p
where extract(year from p.tm_contract_end) = 2026
```

**15. Quels sont les 5 défenseurs centraux avec le plus d'interceptions par 90 minutes cette saison (au moins 900 minutes) ?** (juste)

```sql
select p.player, f.team, f.performance_int_p90
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and p.tm_sub_position = 'Centre-Back' and f.playing_time_min >= 900
order by f.performance_int_p90 desc nulls last
limit 5
```

**16. Quelle est la valeur moyenne des joueurs marocains à la fin de cette saison ?** (juste)

```sql
SELECT
  ROUND(CAST(AVG(f.valeur_fin_saison_eur) / CAST(1e6 AS DECIMAL) AS DECIMAL), 1) AS valeur_moyenne_meur
FROM gold.fact_player_season AS f
JOIN gold.dim_player AS p
  ON p.player_key = f.player_key
WHERE
  p.is_moroccan AND f.season = '2526'
```

**17. Quels sont les 5 joueurs dont la valeur actuelle est la plus loin de leur valeur maximale en carrière ?** (juste)

```sql
SELECT
  p.player,
  p.tm_peak_value_eur,
  p.tm_value_eur,
  ROUND(
    CAST((
      p.tm_peak_value_eur - p.tm_value_eur
    ) / CAST(1e6 AS DECIMAL) AS DECIMAL),
    1
  ) AS ecart_meur
FROM gold.dim_player AS p
WHERE
  p.tm_peak_value_eur IS NOT NULL AND p.tm_value_eur IS NOT NULL
ORDER BY
  ecart_meur DESC NULLS LAST
LIMIT 5
```

**18. Combien de joueurs ont joué pour au moins deux clubs cette saison ?** (juste)

```sql
select count(*) as nb_joueurs
from gold.fact_player_season f
where f.season = '2526' and f.n_clubs >= 2
```

**19. Quel championnat compte le plus de cartons rouges cette saison ?** (juste)

```sql
select f.league, sum(f.performance_crdr) as total_crdr
from gold.fact_player_season f
where f.season = '2526'
group by f.league
order by total_crdr desc nulls last
limit 1
```

**20. Quels sont les 3 attaquants marocains les plus chers actuellement ?** (juste)

```sql
select p.player, f.team, p.tm_value_eur
from gold.dim_player p
join gold.fact_player_season f on f.player_key = p.player_key and f.season = '2526'
where p.tm_position = 'Attack' and p.is_moroccan = true
order by p.tm_value_eur desc nulls last
limit 3
```

**21. Combien de joueurs ont plus de 30 ans cette saison ?** (juste)

```sql
select count(*) as nb_joueurs
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and f.age > 30
```

**22. Quels sont les 3 meilleurs passeurs décisifs de Premier League cette saison ?** (juste)

```sql
select p.player, f.team, f.performance_ast
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and f.league = 'ENG-Premier League'
order by f.performance_ast desc nulls last
limit 3
```

**23. Quelle est la taille moyenne des gardiens ?** (juste)

```sql
select round(avg(tm_height_cm) :: numeric, 2) as taille_moyenne_cm
from gold.dim_player
where tm_position = 'Goalkeeper'
```

**24. Combien de joueurs marocains jouent en Liga cette saison ?** (juste)

```sql
select count(*) as nb_joueurs
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and p.nation_code = 'MAR' and f.league = 'ESP-La Liga'
```

**25. Quel club a le plus de joueurs dans la base cette saison ?** (juste)

```sql
select f.team, count(*) as nb_joueurs
from gold.fact_player_season f
where f.season = '2526'
group by f.team
order by nb_joueurs desc nulls last
limit 1
```

**26. Quels sont les 5 joueurs avec le plus de tirs cadrés par 90 minutes cette saison (au moins 900 minutes) ?** (juste)

```sql
select p.player, f.team, f.standard_sot_p90
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and f.playing_time_min >= 900 and f.standard_sot_p90 is not null
order by f.standard_sot_p90 desc nulls last
limit 5
```

**27. Quelle est la valeur totale des joueurs de chaque championnat à la fin de cette saison ?** (juste)

```sql
select f.league, sum(f.valeur_fin_saison_eur) as valeur_totale_eur
from gold.fact_player_season f
where f.season = '2526' and f.valeur_fin_saison_eur is not null
group by f.league
order by valeur_totale_eur desc
```

**28. Combien de joueurs ont au moins 50 sélections internationales ?** (juste)

```sql
select count(*) as nb_joueurs
from gold.dim_player p
where p.tm_intl_caps >= 50
```

**29. Quel joueur marocain a joué le plus de minutes cette saison ?** (juste)

```sql
select p.player, f.team, f.playing_time_min
from gold.fact_player_season f
join gold.dim_player p on p.player_key = f.player_key
where f.season = '2526' and p.is_moroccan = true
order by f.playing_time_min desc nulls last
limit 1
```

**30. Quelle valeur le modèle prédit-il pour Brahim Díaz cette saison ?** (juste)

```sql
select valeur_predite_eur, valeur_predite_basse_eur, valeur_predite_haute_eur
from ml.valeur_predite
where player = 'Brahim Díaz' and season = '2526'
```

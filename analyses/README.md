# Requêtes d'analyse

Dix questions de scouting traitées en SQL sur le schéma en étoile (`gold`) et sur les prédictions du modèle (`ml`).
Chaque fichier commence par la question posée et la technique SQL utilisée.

| # | Question | Technique |
|---|---|---|
| 01 | Les 3 joueurs les plus chers de chaque championnat | `ROW_NUMBER() OVER (PARTITION BY ...)` |
| 02 | Les plus fortes hausses de valeur sur un an | `LAG()` |
| 03 | Trajectoire de valeur des joueurs marocains | agrégation conditionnelle (pivot), `RANK()` |
| 04 | Les meilleurs buteurs par 90 minutes et leur percentile | `PERCENT_RANK()`, `NTILE()` |
| 05 | Les clubs qui dépendent d'un seul joueur | `SUM() OVER`, `ROW_NUMBER()` |
| 06 | Les jeunes sous-cotés par poste (modèle) | jointure schéma `ml`, `DENSE_RANK()` |
| 07 | Valeur médiane par championnat et tendance | `percentile_cont`, `LAG()`, fenêtre glissante |
| 08 | Effet d'un changement de club sur la valeur | `LAG()`, `CASE`, agrégats |
| 09 | Courbe de valeur selon l'âge et le poste | `percentile_cont`, `HAVING` |
| 10 | Joueurs réguliers et progression de valeur | `STDDEV`, `REGR_SLOPE`, `HAVING` |

```powershell
.\venv\Scripts\python.exe analyses\run.py          # toutes les requêtes, résumé dans docs\analyses_resultats.md
.\venv\Scripts\python.exe analyses\run.py 03 08    # seulement certaines
```

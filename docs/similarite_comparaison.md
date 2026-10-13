# Comparaison des méthodes de similarité

Généré le 2026-10-12 par `ml/similarity_eval.py`.

Test : retrouver un joueur d'une saison à l'autre parmi les joueurs du même poste (voir l'en-tête du script). Plus c'est haut, mieux la méthode capte le style d'un joueur.

## A. 14 championnats, métriques du poste (FBref)

|                       |   hit@1 (%) |   hit@5 (%) |   hit@10 (%) |   MRR |   joueurs testés |
|:----------------------|------------:|------------:|-------------:|------:|-----------------:|
| percentiles + euclid  |        3.19 |       11.39 |        17.6  |  0.08 |             6403 |
| percentiles + cosinus |        2.62 |        9.64 |        15.63 |  0.07 |             6403 |
| z-scores + euclid     |        3.01 |       11.64 |        18.44 |  0.08 |             6403 |
| ACP + euclid          |        3    |       10.7  |        16.96 |  0.08 |             6403 |
| ACP + cosinus         |        2.76 |        9.78 |        16.93 |  0.08 |             6403 |

Hasard : hit@10 de l'ordre de 1.7 %.

## B. 5 grands championnats, métriques du poste (FBref + Understat)

|                       |   hit@1 (%) |   hit@5 (%) |   hit@10 (%) |   MRR |   joueurs testés |
|:----------------------|------------:|------------:|-------------:|------:|-----------------:|
| percentiles + euclid  |        8.16 |       25.06 |        35.38 |  0.17 |             2869 |
| percentiles + cosinus |        7.28 |       22.66 |        32.73 |  0.16 |             2869 |
| z-scores + euclid     |        8.89 |       25.51 |        36.88 |  0.18 |             2869 |
| ACP + euclid          |        8.12 |       23.91 |        35.41 |  0.17 |             2869 |
| ACP + cosinus         |        8.12 |       23.46 |        35.45 |  0.17 |             2869 |

Hasard : hit@10 de l'ordre de 4.1 %.

## C. 5 grands championnats, 17 statistiques pour tous les postes

|                       |   hit@1 (%) |   hit@5 (%) |   hit@10 (%) |   MRR |   joueurs testés |
|:----------------------|------------:|------------:|-------------:|------:|-----------------:|
| percentiles + euclid  |       12.44 |       30.57 |        42.56 |  0.22 |             2869 |
| percentiles + cosinus |       11.33 |       28.16 |        39.18 |  0.21 |             2869 |
| z-scores + euclid     |       13.84 |       31.23 |        42.11 |  0.23 |             2869 |
| ACP + euclid          |       12.3  |       29.38 |        40.89 |  0.22 |             2869 |
| ACP + cosinus         |       12.37 |       29.28 |        40.71 |  0.22 |             2869 |

Hasard : hit@10 de l'ordre de 4.1 %.

## Lecture

- Les méthodes sont proches (1 à 2 points d'écart) et toutes très au-dessus du hasard. L'ACP ne bat ni les percentiles ni les z-scores : avec 5 à 17 statistiques, réduire la dimension apporte peu.
- Les z-scores en distance euclidienne ont un léger avantage sur hit@1 ; les percentiles font aussi bien sur hit@10.
- Ce qui améliore le plus le résultat, c'est le nombre de statistiques (scénario C).
- Le cosinus est moins bon que la distance euclidienne : l'intensité du profil compte, pas seulement sa forme.
- Le dashboard garde les percentiles par défaut (score borné de 0 à 100, lisible, robuste aux valeurs extrêmes) et propose l'ACP + plus proches voisins comme variante.
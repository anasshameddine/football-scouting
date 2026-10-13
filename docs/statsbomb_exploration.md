# StatsBomb Open Data : exploration (13/10/2026)

Source : [StatsBomb Open Data](https://github.com/statsbomb/open-data). Si ces données sont publiées ou présentées, il faut citer StatsBomb comme source et afficher leur logo ([media pack](https://statsbomb.com/media-pack/)).

## Ce qui est disponible

- 80 saisons de compétitions gratuites, 3961 matchs avec compositions.
- Données d'événements (chaque passe, tir, pression, conduite de balle) avec position sur le terrain, et xG de StatsBomb pour chaque tir.
- Ce n'est pas une saison complète des grands championnats : seules quelques saisons et compétitions sont ouvertes, souvent un seul club (Leverkusen 2023-24, Barça en Liga...).

## Joueurs marocains

107 joueurs de nationalité marocaine apparaissent dans les compositions (liste complète : `docs/statsbomb_marocains.csv`). La nationalité est celle indiquée par StatsBomb : elle inclut des binationaux qui jouent pour un autre pays (ex. Munir El Haddadi).

Matchs du Maroc couverts :

- FIFA World Cup 2022 : 7 matchs
- African Cup of Nations 2023 : 4 matchs
- FIFA World Cup 2018 : 3 matchs

Les joueurs les plus présents :

| joueur                |   matchs_maroc | equipes                               |
|:----------------------|---------------:|:--------------------------------------|
| Achraf Hakimi Mouh    |             14 | Morocco / Paris Saint-Germain         |
| Yassine Bounou        |             14 | Girona / Morocco / Sevilla            |
| Youssef En-Nesyri     |             14 | Leganés / Morocco / Sevilla           |
| Munir Mohand Mohamedi |             14 | Morocco                               |
| Sofyan Amrabat        |             14 | Morocco                               |
| Romain Saïss          |             13 | Angers / Morocco                      |
| Hakim Ziyech          |             13 | Morocco                               |
| Azzedine Ounahi       |             11 | Morocco / Olympique de Marseille      |
| Abdessamad Ezzalzouli |             11 | Morocco                               |
| Bilal El Khannous     |             11 | Morocco                               |
| Sofiane Boufal        |             10 | Angers / Celta Vigo / Lille / Morocco |
| Nayef Aguerd          |             10 | Morocco / Rennes                      |
| Selim Amallah         |             10 | Morocco                               |
| Yahia Attiyat allah   |             10 | Morocco                               |
| Ahmed Reda Tagnaouti  |              9 | Morocco                               |

## Statistiques par joueur sur les matchs du Maroc (événements)

|                     |   passes |   passes_reussies |   passes_cles |   pressions |   conduites |   tirs |   xg |   buts |   tacles |   dribbles |   interceptions |
|:--------------------|---------:|------------------:|--------------:|------------:|------------:|-------:|-----:|-------:|---------:|-----------:|----------------:|
| Achraf Hakimi Mouh  |      762 |               630 |            23 |         208 |         576 |     12 | 2.01 |      2 |       42 |         20 |              14 |
| Hakim Ziyech        |      549 |               393 |            20 |         235 |         515 |     27 | 1.87 |      3 |       19 |         53 |              24 |
| Sofyan Amrabat      |      537 |               472 |             3 |         196 |         405 |      1 | 0.02 |      0 |       29 |          2 |              10 |
| Azzedine Ounahi     |      484 |               417 |            12 |         128 |         468 |     13 | 0.74 |      1 |       13 |         24 |              11 |
| Romain Saïss        |      457 |               383 |             2 |          64 |         315 |      3 | 1.1  |      2 |       18 |          1 |              12 |
| Nayef Aguerd        |      423 |               382 |             2 |          34 |         316 |      2 | 0.32 |      0 |       12 |          0 |               6 |
| Yassine Bounou      |      325 |               245 |             0 |           2 |         150 |      0 | 0    |      0 |        0 |          0 |               0 |
| Yahia Attiyat allah |      200 |               146 |             5 |          46 |         141 |      2 | 0.33 |      0 |        5 |          3 |               3 |
| Sofiane Boufal      |      198 |               160 |             9 |         109 |         241 |     11 | 0.63 |      0 |       13 |         30 |               4 |
| Jawad El Yamiq      |      160 |               143 |             0 |          18 |         123 |      1 | 0.06 |      0 |        4 |          0 |               5 |
| Noussair Mazraoui   |      155 |               130 |             2 |          49 |         106 |      4 | 0.15 |      0 |       17 |          2 |               1 |
| Selim Amallah       |      134 |               106 |             3 |         146 |         136 |      3 | 0.19 |      0 |       15 |         12 |              13 |

Colonnes : tirs, xG (somme des xG StatsBomb), passes (réussies, clés), pressions, tacles, interceptions, conduites de balle, dribbles. Calcul sur 14 matchs du Maroc au plus par joueur.

## Recoupement avec notre base

22 joueurs StatsBomb sur 107 sont déjà dans `joueurs_propres.csv`.

## Verdict

- **Utile** : fiches avec carte des tirs, xG réel par tir et réseau de passes de l'équipe nationale (Coupe du monde 2018 et 2022, CAN 2023). Donnée de bien meilleure qualité que FBref pour le détail.
- **Limite** : 3 tournois seulement (14 matchs du Maroc au plus par joueur), pas de saison de club complète pour les Marocains. Impossible d'alimenter le modèle de valeur ni les percentiles de saison.
- **Choix** : source complémentaire, affichée dans la fiche joueur quand elle existe, jamais mélangée aux statistiques de saison. Indiquer clairement « équipe nationale, tournois uniquement ».
# Modèle de valeur marchande : résultats

Généré le 2026-10-13. Test = saison 2025-26, jamais vue pendant le réglage.

| essai                            |   R² test |   Erreur médiane test (%) |   Part à ±50 % test (%) |   RMSE log test |   R² validation |   Erreur médiane validation (%) |
|:---------------------------------|----------:|--------------------------:|------------------------:|----------------:|----------------:|--------------------------------:|
| 1. Ridge (linéaire, avec club)   |      0.84 |                     36.23 |                   66.61 |            0.62 |            0.82 |                           36.38 |
| 2. XGBoost (sans niveau du club) |      0.74 |                     46.4  |                   54.03 |            0.8  |            0.73 |                           46.21 |
| 3. XGBoost (avec niveau du club) |      0.88 |                     31.61 |                   72.27 |            0.54 |            0.87 |                           32.07 |

## Erreur par poste (test)

| tm_sub_position    |   joueurs |   erreur_mediane_pct |   biais_mediane_pct |
|:-------------------|----------:|---------------------:|--------------------:|
| Centre-Back        |       901 |                 31.5 |                -6.3 |
| Central Midfield   |       591 |                 32.4 |                -8.3 |
| Centre-Forward     |       590 |                 32.6 |                -4.6 |
| Right-Back         |       391 |                 28.9 |                -1.4 |
| Defensive Midfield |       368 |                 31.5 |                -4.7 |
| Left-Back          |       350 |                 28.6 |                -2.1 |
| Left Winger        |       340 |                 33.3 |                -2   |
| Right Winger       |       313 |                 32.3 |                -9.1 |
| Attacking Midfield |       278 |                 32   |                -3.1 |
| Right Midfield     |        60 |                 28.2 |                 3.2 |
| Left Midfield      |        38 |                 31.2 |                15.9 |
| Second Striker     |        18 |                 31.1 |                -1.8 |

## Erreur par palier de valeur (test)

| palier        |   joueurs |   erreur_mediane_pct |   biais_mediane_pct |
|:--------------|----------:|---------------------:|--------------------:|
| moins de 5 M€ |      2623 |                 32.6 |                 7.5 |
| 5 à 25 M€     |      1165 |                 32.4 |               -19.2 |
| 25 à 70 M€    |       398 |                 25.5 |               -20.3 |
| plus de 70 M€ |        52 |                 32.3 |               -32.3 |

## Variables les plus utiles

|                          |   importance_pct |
|:-------------------------|-----------------:|
| equipe_log_valeur_autres |             30.8 |
| us_xg_chain_p90          |             12.7 |
| age                      |              6.6 |
| ligue_ENG-Premier League |              6   |
| minutes                  |              4.3 |
| us_np_xg_p90             |              3.7 |
| ligue_SCO-Premiership    |              2.1 |
| ligue_KSA-Pro League     |              2   |
| part_titulaire           |              1.8 |
| big5                     |              1.7 |
| performance_gls_p90      |              1.6 |
| poste_Right-Back         |              1.6 |

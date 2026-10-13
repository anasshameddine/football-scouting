![CI](https://github.com/anasshameddine/football-scouting/actions/workflows/ci.yml/badge.svg)

# Scouting football : plateforme de données et dashboard

Trouver les joueurs au profil le plus proche d'un joueur de référence, classés par budget
(valeur Transfermarkt), avec un focus sur les joueurs marocains.

## Architecture (en construction)

```
FBref / Understat / Transfermarkt / StatsBomb
        -> ingestion (Python, Parquet) -> stockage S3 (bronze)
        -> PostgreSQL -> dbt (silver, gold en étoile)
        -> ml (similarité, valeur marchande) -> API FastAPI
        -> dashboard Streamlit + assistant text-to-SQL
```

| Dossier | Rôle |
|---|---|
| `ingestion/` | Collecte des sources et rapprochement des identifiants |
| `dbt/` | Modèles silver et gold, tests |
| `ml/` | Similarité par percentiles, modèle de valeur |
| `api/` | Routes FastAPI |
| `app/` | Dashboard Streamlit |
| `assistant/` | Assistant : texte vers SQL, RAG sur Wikipédia, rapports (Ollama) |
| `airflow/` | DAG de planification |
| `analyses/` | Requêtes SQL d'analyse |
| `docs/` | Schémas, notes sur les sources |

## Orchestration (Airflow)

Le DAG `scouting_pipeline` (`airflow/dags/scouting_pipeline.py`) enchaîne les mêmes étapes que `run_pipeline.ps1`,
chaque lundi à 06 h : collecte FBref et Understat, chargement PostgreSQL, rapprochement, `dbt run`, `dbt test`,
puis exports et modèle de valeur. Deux tentatives de reprise par tâche ; si `dbt test` échoue, rien n'est exporté.

```powershell
docker compose --profile airflow up -d --build   # première fois : image de 1 à 2 Go
# http://localhost:8080  (admin / admin)
```

Lancer le DAG à la main depuis l'interface (bouton « Trigger DAG w/ config » pour choisir la saison).
Airflow utilise SQLite et le `SequentialExecutor` : suffisant pour un projet perso, à remplacer par
PostgreSQL et `LocalExecutor` en production.

## Démarrage

```powershell
copy .env.example .env
docker compose up -d
python -m streamlit run app\app.py
```

Console S3 : http://localhost:9001. PostgreSQL : localhost:5432.

## Lancer le pipeline

```powershell
docker compose up -d
python ingestion\bronze_load.py                      # fichiers locaux -> bronze (S3)
python ingestion\collect_bronze.py --source fbref --saisons 2024-2025   # nouvelles saisons
.\run_pipeline.ps1                                    # bronze -> PostgreSQL -> dbt -> export
python -m streamlit run app\app.py
```

Chaque étape est idempotente : relancer ne crée pas de doublons.

| Couche | Où | Contenu |
|---|---|---|
| bronze | S3 (Parquet) | données brutes par source, saison et championnat |
| raw | PostgreSQL `raw` | bronze chargé tel quel |
| mapping | PostgreSQL `mapping` | rapprochement des noms entre FBref, Understat, Transfermarkt |
| silver | PostgreSQL `silver` | nettoyage, typage, dédoublonnage, regroupement des transferts |
| gold | PostgreSQL `gold` | schéma en étoile (`dim_*`, `fact_*`) et `mart_scouting` pour le dashboard |

## Modèle de valeur marchande

XGBoost sur le logarithme de la valeur Transfermarkt de fin de saison. Entraînement 2021-22 à
2023-24, validation 2024-25, test 2025-26 (jamais vue). Les résultats détaillés sont dans
`docs/modele_valeur_resultats.md`, les essais dans MLflow :

```powershell
.\venv\Scripts\mlflow.exe ui --backend-store-uri sqlite:///mlflow.db
```

Limites : la valeur Transfermarkt est une estimation arrondie ; le modèle ignore blessures,
fin de contrat et réputation ; il sous-estime les très hautes valeurs.

## Fiche joueur

Cliquer sur un nom (listes, sous-cotés, tableaux : colonne « Fiche ») ouvre sa page : photo et biographie Wikipédia
(API publique, la photo reste hébergée par Wikimedia), valeur Transfermarkt et estimation du modèle avec sa fourchette,
statistiques de chaque saison (totaux et par 90 minutes), évolution de la valeur, radar de percentiles et joueurs similaires.
L'adresse de la fiche est partageable (`?joueur=<id Transfermarkt>`). Les homonymes sont départagés par l'année de
naissance et le club cités dans l'article ; sans page Wikipédia, la fiche s'affiche sans biographie.

## Similarité

Deux méthodes, au choix dans le dashboard et dans l'API (`method=percentiles|pca`) :
- **Percentiles par poste** (défaut) : chaque statistique devient un percentile dans le poste, la similarité est la distance entre profils ramenée sur 100.
- **ACP + plus proches voisins** : statistiques centrées-réduites, ACP gardant 90 % de la variance, distance euclidienne.

`ml/similarity_eval.py` les compare sur un test objectif (retrouver un joueur d'une saison à l'autre) : voir `docs/similarite_comparaison.md`. Les deux sont proches et très au-dessus du hasard ; l'ACP ne fait pas mieux que les percentiles, qui restent le défaut pour leur lisibilité.

## API

FastAPI, qui réutilise `ml/features.py`, `ml/profiles.py` et le modèle sauvegardé (pas de code dupliqué).

```powershell
.\venv\Scripts\python.exe -m uvicorn api.main:app --reload   # http://localhost:8000/docs
.\venv\Scripts\python.exe -m pytest                          # tous les tests du projet
docker compose --profile api up --build api                     # version conteneurisée
```

| Route | Rôle |
|---|---|
| `POST /predict-value` | valeur prédite et fourchette à 80 %, pour un joueur connu ou des caractéristiques saisies |
| `GET /similar-players` | joueurs proches, au global et par tranche de budget (filtres âge, Marocains) |
| `GET /undervalued` | joueurs sous-cotés de la dernière saison |
| `GET /health` | état et métriques du modèle |

## Assistant (Ollama, local et gratuit)

Page « Assistant IA » du dashboard, et onglet « Rapport de scouting (IA) » de chaque fiche joueur.

| Partie | Fonctionnement |
|---|---|
| Questions chiffrées | le modèle écrit une requête SQL sur le schéma gold (décrit dans `assistant/schema.py`), vérifiée (une seule lecture, tables autorisées, mots interdits) puis exécutée en transaction **lecture seule** avec délai de 10 s ; en cas d'erreur PostgreSQL ou de résultat vide, l'erreur est renvoyée au modèle qui corrige (3 essais). La requête est toujours affichée. |
| Biographies | articles Wikipédia complets découpés en passages, vecteurs `bge-m3` (multilingue : question en français, article en anglais) dans **pgvector** ; si la question cite un joueur, la recherche se limite à sa biographie (indexée à la volée si elle manque) ; réponse avec sources numérotées. |
| Rapport de scouting | le modèle rédige 8 sections fixes à partir de faits calculés par le projet (stats, percentiles, valeur, estimation, joueurs proches) ; chaque nombre du rapport est comparé aux faits et les nombres absents sont signalés. |

```powershell
ollama pull qwen2.5:7b ; ollama pull bge-m3          # une fois (environ 6 Go)
.\venv\Scripts\python.exe -m assistant.rag --limite 500     # indexer les biographies (Marocains d'abord)
.\venv\Scripts\python.exe -m assistant.rag --statut              # joueurs indexés, Marocains sans page
.\venv\Scripts\python.exe -m assistant.rag --tester "Hakimi"     # diagnostic Wikipédia d'un joueur
.\venv\Scripts\python.exe -m assistant.evaluer              # précision sur 20 questions -> docs/assistant_evaluation.md
```

Wikipédia : une requête par joueur, au plus une par seconde, pause automatique si Wikipédia répond « 429 » ; mettre un contact dans `WIKI_CONTACT` (`.env`) comme le demande Wikimedia.
Sécurité : `assistant/sql/role_lecture.sql` crée un rôle PostgreSQL qui n'a que le droit SELECT (à mettre dans `ASSISTANT_DB_URL`).
Modèles modifiables dans `.env` : `OLLAMA_MODEL` (ex. `qwen2.5:3b` sur un ordinateur modeste), `OLLAMA_EMBED_MODEL`.

## État d'avancement

- [x] Collecte et nettoyage (14 championnats, saison 2025-2026)
- [x] Similarité, archétypes, tranches de budget
- [x] Dashboard Streamlit
- [x] Docker (PostgreSQL, S3), bronze Parquet, PostgreSQL raw, dbt silver et gold, tests
- [x] Modèle de valeur marchande (XGBoost, MLflow), joueurs sous-cotés
- [x] API FastAPI (Swagger, pytest, Docker)
- [x] Dashboard bilingue FR/EN : page sous-cotés, estimation sur la fiche joueur (avec avertissement au-dessus de 50 M€), évolution de la valeur
- [x] Variante ACP + plus proches voisins, comparée aux percentiles
- [x] 10 requêtes SQL d'analyse (`analyses/`)
- [x] Fiche joueur : statistiques par saison, valeur, prédiction, biographie et photo
- [x] Assistant : texte vers SQL (lecture seule), RAG Wikipédia avec pgvector, rapports de scouting, 20 questions de test
- [ ] Airflow, CI, GitHub

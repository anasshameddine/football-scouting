"""
DAG « scouting_pipeline » : tout le pipeline de données, chaque lundi à 06 h.

    collecte FBref + Understat (bronze, S3)
        -> chargement PostgreSQL (raw) -> rapprochement des identifiants
        -> dbt run -> dbt test
        -> export dashboard    et    export base ML -> modèle de valeur

Chaque tâche appelle les mêmes scripts que run_pipeline.ps1 : le DAG ne contient pas de logique métier,
seulement l'ordre, les reprises en cas d'échec et la planification.
Si dbt test échoue, rien n'est exporté : le dashboard garde les dernières données valides.

Lancement manuel avec une autre saison : « Trigger DAG w/ config » et le paramètre `saison`.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup

PROJET = "/opt/project"
PY = "/home/airflow/venv-projet/bin/python"
DBT = "/home/airflow/venv-projet/bin/dbt"

default_args = {
    "owner": "scouting",
    "retries": 2,                       # une panne réseau passagère ne doit pas faire échouer la semaine
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="scouting_pipeline",
    description="Bronze -> PostgreSQL -> dbt -> exports -> modèle de valeur",
    schedule="0 6 * * 1",               # chaque lundi à 06:00
    start_date=datetime(2025, 8, 1),
    catchup=False,                      # pas de rattrapage des semaines passées
    max_active_runs=1,
    default_args=default_args,
    params={"saison": "2025-2026"},
    tags=["scouting", "data-engineering"],
    doc_md=__doc__,
) as dag:

    def tache(task_id, commande, **kw):
        return BashOperator(task_id=task_id, bash_command=commande, cwd=PROJET, **kw)

    with TaskGroup("bronze", tooltip="Collecte des sources vers le bucket S3") as bronze:
        # --force : la saison en cours change chaque semaine, on la retélécharge ; les anciennes ne sont pas touchées
        fbref = tache("fbref", f"{PY} ingestion/collect_bronze.py --source fbref --saisons {{{{ params.saison }}}} --force")
        understat = tache("understat",
                          f"{PY} ingestion/collect_bronze.py --source understat --saisons {{{{ params.saison }}}} --force")

    charger = tache("load_postgres", f"{PY} ingestion/load_postgres.py")
    rapprocher = tache("matching", f"{PY} ingestion/matching.py")
    dbt_run = tache("dbt_run", f"cd dbt && {DBT} run --profiles-dir .")
    dbt_test = tache("dbt_test", f"cd dbt && {DBT} test --profiles-dir .")
    export_mart = tache("export_mart", f"{PY} ml/export_mart.py")
    export_ml = tache("export_ml_base", f"{PY} ml/export_ml_base.py")
    modele = tache("train_value", f"{PY} ml/train_value.py --pg", execution_timeout=timedelta(hours=1))

    bronze >> charger >> rapprocher >> dbt_run >> dbt_test >> [export_mart, export_ml]
    export_ml >> modele

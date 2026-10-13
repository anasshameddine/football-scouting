"""Vérifie la structure du DAG sans lancer Airflow en entier (ignoré si Airflow n'est pas installé)."""

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("airflow.models")   # le dossier airflow/ du projet ne doit pas passer pour la bibliothèque

DAG_FILE = Path(__file__).resolve().parents[1] / "dags" / "scouting_pipeline.py"


@pytest.fixture(scope="module")
def dag():
    spec = importlib.util.spec_from_file_location("scouting_pipeline", DAG_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.dag


def test_dag_se_charge_avec_les_bonnes_taches(dag):
    assert set(dag.task_ids) == {"bronze.fbref", "bronze.understat", "load_postgres", "matching", "dbt_run",
                                 "dbt_test", "export_mart", "export_ml_base", "train_value"}
    assert dag.catchup is False and dag.max_active_runs == 1


def test_ordre_des_taches(dag):
    assert dag.get_task("load_postgres").upstream_task_ids == {"bronze.fbref", "bronze.understat"}
    assert dag.get_task("dbt_test").downstream_task_ids == {"export_mart", "export_ml_base"}
    assert dag.get_task("train_value").upstream_task_ids == {"export_ml_base"}


def test_les_scripts_appeles_existent(dag):
    racine = DAG_FILE.parents[2]
    for t in dag.tasks:
        for mot in t.bash_command.split():
            if mot.endswith(".py"):
                assert (racine / mot).exists(), mot

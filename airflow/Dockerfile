# Airflow 2.x + un environnement Python séparé pour le pipeline (dbt, xgboost, mlflow...),
# afin que les dépendances du projet ne rentrent pas en conflit avec celles d'Airflow.
FROM apache/airflow:2.11.2-python3.12
COPY requirements-pipeline.txt /tmp/requirements-pipeline.txt
RUN python -m venv /home/airflow/venv-projet \
 && /home/airflow/venv-projet/bin/pip install --no-cache-dir -r /tmp/requirements-pipeline.txt
RUN mkdir -p /opt/airflow/db

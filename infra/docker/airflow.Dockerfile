FROM apache/airflow:2.10.5-python3.11

COPY --chown=airflow:root pyproject.toml README.md /opt/airflow/project/
COPY --chown=airflow:root src /opt/airflow/project/src
RUN pip install --no-cache-dir /opt/airflow/project

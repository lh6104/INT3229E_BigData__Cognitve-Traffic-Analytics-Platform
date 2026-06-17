.PHONY: help up down pipeline ingest-once stream-test airflow-test dq-check train notebook-check mlflow-test neo4j-import graph-test api-smoke benchmark frontend-smoke test ci-local logs ps create-topics docker-api docker-test

COMPOSE_CMD := docker compose -f docker-compose.yml
PYTHON ?= /home/longha/miniforge3/envs/traffic/bin/python
RAW_DIR ?= raw
DATA_DIR ?= data
API_BASE_URL ?= http://localhost:8000
KAFKA_BOOTSTRAP_SERVERS ?= localhost:9092
MLFLOW_TRACKING_URI ?= http://localhost:5000
MLFLOW_EXPERIMENT_NAME ?= cognitive-traffic-local-artifacts

help:
	@echo "Cognitive Traffic Analytics Platform"
	@echo "  make up              Start local production-like stack"
	@echo "  make down            Stop stack"
	@echo "  make pipeline        Build Bronze/Silver/Gold local datasets and run DQ"
	@echo "  make ingest-once     Fetch one raw snapshot cycle when API keys are configured"
	@echo "  make stream-test     Produce/consume bounded Kafka messages into Bronze JSONL"
	@echo "  make airflow-test    Validate production-like Airflow DAG"
	@echo "  make dq-check        Run Gold data quality gate"
	@echo "  make train           Train local models and log to MLflow when available"
	@echo "  make notebook-check  Execute the training notebook with nbconvert"
	@echo "  make mlflow-test     Verify MLflow tracking server"
	@echo "  make neo4j-import    Import Gold segment graph into Neo4j"
	@echo "  make graph-test      Verify Neo4j graph and graph API"
	@echo "  make api-smoke       Verify FastAPI health/model/graph endpoints"
	@echo "  make benchmark       Benchmark local API endpoints and write performance reports"
	@echo "  make frontend-smoke  Build React frontend"
	@echo "  make test            Run lightweight pytest suite"
	@echo "  make ci-local        Run local CI checks"

up:
	$(COMPOSE_CMD) up -d --build

down:
	$(COMPOSE_CMD) down

logs:
	$(COMPOSE_CMD) logs -f

ps:
	$(COMPOSE_CMD) ps

create-topics:
	$(COMPOSE_CMD) exec kafka kafka-topics --create --if-not-exists --topic traffic.raw --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
	$(COMPOSE_CMD) exec kafka kafka-topics --create --if-not-exists --topic weather.raw --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
	$(COMPOSE_CMD) exec kafka kafka-topics --create --if-not-exists --topic news.raw --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

pipeline:
	$(PYTHON) -m pipelines.transformation.run_local_pipeline --raw-dir $(RAW_DIR) --output-dir $(DATA_DIR)
	$(PYTHON) -m pipelines.quality.run_checks --layer gold --input $(DATA_DIR)/gold/cleaned_traffic_features --output reports/data_quality_report.md

ingest-once:
	$(PYTHON) scripts/ingest_raw_sources.py --raw-dir $(RAW_DIR) --once

stream-test:
	$(PYTHON) -m pipelines.streaming.bounded_ingest --bootstrap-servers $(KAFKA_BOOTSTRAP_SERVERS) --raw-dir $(RAW_DIR) --output $(DATA_DIR)/bronze/streaming_bounded_test.jsonl --reset-output --inject-invalid

airflow-test:
	$(PYTHON) -m pipelines.orchestration.airflow_dag_smoke

dq-check:
	$(PYTHON) -m pipelines.quality.run_checks --layer gold --input $(DATA_DIR)/gold/cleaned_traffic_features --output reports/data_quality_report.md

train:
	MLFLOW_TRACKING_URI=$(MLFLOW_TRACKING_URI) MLFLOW_EXPERIMENT_NAME=$(MLFLOW_EXPERIMENT_NAME) $(PYTHON) -m ml.training.train_cli --input $(DATA_DIR)/gold/train_features_15m.parquet --output-dir models/artifacts --metadata-dir models/metadata --experiment-name $(MLFLOW_EXPERIMENT_NAME)

notebook-check:
	$(PYTHON) -c "import importlib.util, subprocess, sys; sys.exit(subprocess.call([sys.executable, '-m', 'jupyter', 'nbconvert', '--to', 'notebook', '--execute', 'notebooks/01_train_traffic_forecasting_model.ipynb', '--output', 'executed_train_model.ipynb', '--output-dir', '/tmp']) if importlib.util.find_spec('nbconvert') else subprocess.call([sys.executable, 'scripts/check_training_notebook.py', 'notebooks/01_train_traffic_forecasting_model.ipynb']))"

mlflow-test:
	$(PYTHON) -m ml.tracking.mlflow_smoke --tracking-uri $(MLFLOW_TRACKING_URI) --experiment $(MLFLOW_EXPERIMENT_NAME)

neo4j-import:
	$(PYTHON) -m graph.neo4j.import_graph --limit 200

graph-test:
	$(PYTHON) -m graph.neo4j.graph_smoke --api-url $(API_BASE_URL)

api-smoke:
	$(PYTHON) scripts/demo_check.py --base-url $(API_BASE_URL)

benchmark:
	$(PYTHON) scripts/benchmark_api.py --base-url $(API_BASE_URL)

frontend-smoke:
	cd frontend && npm run build

test:
	$(PYTHON) -c "import pathlib; files='api/main.py api/routers/graph.py api/routers/model.py api/services/graph_service.py pipelines/transformation/manifest.py pipelines/streaming/bounded_ingest.py pipelines/quality/run_checks.py graph/neo4j/import_graph.py ml/tracking/mlflow_smoke.py ml/tracking/mlflow_utils.py ml/training/features.py ml/training/metrics.py ml/training/model_io.py ml/training/train_utils.py ml/training/train_cli.py ml/serving/predict.py scripts/benchmark_api.py scripts/check_training_notebook.py scripts/train_local_api_models.py'.split(); [compile(pathlib.Path(f).read_text(encoding='utf-8'), f, 'exec') for f in files]"
	$(MAKE) notebook-check
	$(PYTHON) -m pipelines.orchestration.airflow_dag_smoke
	$(PYTHON) -m pipelines.quality.run_checks --layer gold --input $(DATA_DIR)/gold/cleaned_traffic_features --output reports/data_quality_report.md
	$(PYTHON) -c "import importlib.util, subprocess, sys; sys.exit(subprocess.call([sys.executable, '-m', 'pytest']) if importlib.util.find_spec('pytest') else 0)"

ci-local: airflow-test pipeline dq-check notebook-check test frontend-smoke

docker-api:
	$(COMPOSE_CMD) up --build api

docker-test:
	$(COMPOSE_CMD) run --build --rm api make test

.DEFAULT_GOAL := help

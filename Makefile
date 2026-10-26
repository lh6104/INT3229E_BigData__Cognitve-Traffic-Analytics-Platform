.PHONY: help bootstrap up down up-ingestion up-streaming up-inference up-orchestration up-ml replay test test-unit lint api frontend smoke oncall-demo

CONDA_ENV ?= traffic
CONDA ?= conda
PYTHON := $(CONDA) run -n $(CONDA_ENV) python
COMPOSE := docker compose
START ?=
END ?=
DATASET ?=

help:
	@echo "Cognitive Traffic"
	@echo "  make bootstrap          Create/update the Python 3.11 Conda environment"
	@echo "  make up                 Start the core local stack"
	@echo "  make up-ingestion       Add traffic, weather, and news ingestion"
	@echo "  make up-streaming       Add the event-time feature processor"
	@echo "  make up-inference       Add forecast inference (model variables required)"
	@echo "  make up-orchestration   Add Airflow"
	@echo "  make test               Run all tests (Docker or TRAFFIC_TEST_DSN required)"
	@echo "  make test-unit          Run fast checks without real PostgreSQL"
	@echo "  make lint               Run Ruff and compile checks"
	@echo "  make smoke              Verify isolated persistence, browser and telemetry"
	@echo "  make oncall-demo        Include isolated alert-driven API recovery"

bootstrap:
	./scripts/bootstrap.sh $(CONDA_ENV)

up:
	$(COMPOSE) up -d --build --wait --wait-timeout 180

up-ingestion:
	$(COMPOSE) --profile ingestion up -d --build

up-streaming:
	$(COMPOSE) --profile streaming up -d --build

up-inference:
	@test -n "$(MODEL_ARTIFACT_KEY)" || (echo "MODEL_ARTIFACT_KEY is required" && exit 2)
	@test -n "$(MODEL_VERSION)" || (echo "MODEL_VERSION is required" && exit 2)
	MODEL_ARTIFACT_KEY="$(MODEL_ARTIFACT_KEY)" MODEL_VERSION="$(MODEL_VERSION)" $(COMPOSE) --profile inference up -d --build

up-orchestration:
	$(COMPOSE) --profile orchestration up -d --build

down:
	$(COMPOSE) --profile ingestion --profile streaming --profile inference --profile orchestration --profile ml down

replay:
	@test -n "$(START)" || (echo "START is required" && exit 2)
	@test -n "$(END)" || (echo "END is required" && exit 2)
	$(PYTHON) -m cognitive_traffic.streaming.replay --start "$(START)" --end "$(END)" $(if $(DATASET),--dataset "$(DATASET)",)

test:
	$(PYTHON) scripts/run_tests.py

test-unit:
	$(PYTHON) -m pytest --ignore=tests/integration/test_serving_persistence.py
	node --test frontend/tests/*.test.mjs

smoke:
	$(PYTHON) scripts/compose_smoke.py

oncall-demo:
	$(PYTHON) scripts/compose_smoke.py --oncall

up-ml:
	$(COMPOSE) --profile ml up -d --build

lint:
	$(PYTHON) -m ruff check src tests orchestration scripts
	$(PYTHON) -m compileall -q src orchestration scripts

api:
	$(PYTHON) -m uvicorn cognitive_traffic.api.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

.DEFAULT_GOAL := help

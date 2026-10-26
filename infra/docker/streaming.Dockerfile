FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

ARG PROJECT_EXTRAS=streaming
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
RUN pip install --no-cache-dir ".[${PROJECT_EXTRAS}]"

CMD ["python", "-m", "cognitive_traffic.streaming.processors", "normalize"]

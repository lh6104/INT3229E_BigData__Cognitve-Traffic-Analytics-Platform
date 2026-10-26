FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY infra/postgres ./infra/postgres
COPY constraints ./constraints
RUN pip install --no-cache-dir -c constraints/python311.txt ".[api]" && pip check

EXPOSE 8000
CMD ["uvicorn", "cognitive_traffic.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

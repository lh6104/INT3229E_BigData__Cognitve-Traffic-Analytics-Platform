FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY infra/postgres ./infra/postgres
COPY constraints ./constraints
RUN pip install --no-cache-dir -c constraints/python311.txt ".[api]" && pip check
COPY infra/docker/api-entrypoint.sh /app/api-entrypoint.sh
RUN chmod +x /app/api-entrypoint.sh

EXPOSE 8000
CMD ["/app/api-entrypoint.sh"]

# Build context MUST be the repo root:
#   docker build -f docker/api.Dockerfile -t biomac-api .
# (the app imports as `api.app.*`, so `api/` has to land at /app/api)

FROM python:3.13-slim AS builder
WORKDIR /app
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r api/requirements.txt

FROM python:3.13-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /install /usr/local
COPY api/ ./api/
COPY champion_output.json ./champion_output.json

# BIOMAC_DB_PATH defaults to a relative "runtime/biomac.db"; /app is
# root-owned from the COPY steps above, so the non-root user below can't
# mkdir into it unless we create+chown it first. In ECS this directory is
# overridden by an EFS mount instead (BIOMAC_DB_PATH=/mnt/efs/db/biomac.db,
# EFS access point owned by uid/gid 10001) -- this local dir is what makes
# `docker run` work standalone too, e.g. for local smoke tests.
RUN mkdir -p /app/runtime && chown -R appuser:appuser /app/runtime

ENV BIOMAC_FUNCTIONAL_CHAMPION_OUTPUT=/app/champion_output.json \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8001

# api.app.main:app is intentionally NOT used here -- it leaves the
# monthly-run orchestrator/persistence unwired and POST /api/v2/monthly-runs
# returns 503. api.app.functional:app is the fully-composed app.
CMD ["uvicorn", "api.app.functional:app", "--host", "0.0.0.0", "--port", "8001"]

FROM python:3.12-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY packages/novel-engine /workspace/packages/novel-engine
COPY apps/api /workspace/apps/api

WORKDIR /workspace/apps/api

RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e /workspace/packages/novel-engine \
    && pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

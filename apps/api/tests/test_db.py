import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_database_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health/db")
    if response.status_code == 503:
        pytest.fail(
            "database is not reachable; start Postgres with "
            "`docker compose up db -d` and retry"
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}

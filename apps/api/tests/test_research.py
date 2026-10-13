from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.api.schemas import ResearchSessionOut
from app.main import app


def test_research_session_and_stage_progress_are_persisted() -> None:
    with TestClient(app) as client:
        created = client.post("/projects", json={"title": f"Research {uuid.uuid4().hex[:8]}"})
        assert created.status_code == 201
        project_id = created.json()["id"]
        try:
            initial = client.get(f"/projects/{project_id}/research")
            assert initial.status_code == 200
            assert initial.json()["status"] == "idle"
            assert len(initial.json()["stages"]) == 6

            added = client.post(
                f"/projects/{project_id}/research/sources",
                json={"title": "参考作品 A", "path": "samples/book-a.md"},
            )
            assert added.status_code == 201
            assert added.json()["sources"][0]["title"] == "参考作品 A"

            started = client.post(f"/projects/{project_id}/research/start")
            assert started.status_code == 200
            assert started.json()["status"] == "running"
            assert started.json()["stages"][0]["status"] == "running"

            completed = client.post(
                f"/projects/{project_id}/research/stages/ingest",
                json={"status": "done", "output": "已切分 24 章"},
            )
            assert completed.status_code == 200
            body = completed.json()
            assert body["progress"] == 17
            assert body["stages"][0]["output"] == "已切分 24 章"
            assert body["stages"][1]["status"] == "running"
        finally:
            client.delete(f"/projects/{project_id}")


def test_research_session_accepts_injection_metadata() -> None:
    session = ResearchSessionOut.model_validate(
        {
            "status": "completed",
            "progress": 100,
            "stages": [],
            "sources": [],
            "artifacts": [],
            "injection_approved_by": "studio-user",
            "injection_note": "Approved from research workspace",
            "creative_profile": {"style_guide": "Short, tense prose."},
        }
    )

    assert session.injection_note == "Approved from research workspace"
    assert session.creative_profile == {"style_guide": "Short, tense prose."}

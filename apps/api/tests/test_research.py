from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.adapters.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.api.routes import research as research_routes
from app.api.schemas import CreationPitch, ProjectFinalizeCreation, ResearchBinding, ResearchSessionOut
from app.core.config import get_settings
from app.db.models.project import NovelProject as NovelProjectRow
from app.db.session import get_session_factory
from app.main import app
from novel_engine.models.entities import NovelProject, StoryBible
from novel_engine.models.enums import ProjectStatus


def test_research_session_and_stage_progress_are_persisted() -> None:
    with TestClient(app) as client:
        created = client.post("/projects", json={"title": f"Research {uuid.uuid4().hex[:8]}"})
        assert created.status_code == 201
        assert created.json()["status"] == "draft"
        project_id = created.json()["id"]
        try:
            initial = client.get(f"/projects/{project_id}/research")
            assert initial.status_code == 200
            assert initial.json()["status"] == "idle"
            assert len(initial.json()["stages"]) == 5

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
            assert body["progress"] == 20
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


def test_title_suggestion_requires_research_binding() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/projects/title-suggestion",
            json={"genre": "mystery", "language": "en"},
        )
        assert response.status_code in {400, 422}


def test_framework_proposal_requires_completed_research() -> None:
    with TestClient(app) as client:
        created = client.post("/projects", json={"title": f"Framework {uuid.uuid4().hex[:8]}"})
        assert created.status_code == 201
        project_id = created.json()["id"]
        try:
            response = client.post(
                f"/projects/{project_id}/framework-proposal",
                json={
                    "premise": "A translator finds a coded confession.",
                    "theme": "Truth has a cost",
                    "logline": "One confession changes everything.",
                    "synopsis": "A translator follows the confession to its hidden author.",
                    "research_binding": {"session_id": "missing", "source_ids": ["source-1"]},
                },
            )
            assert response.status_code == 422
            assert "研究" in response.json()["error"]["message"]
        finally:
            client.delete(f"/projects/{project_id}")


@pytest.mark.asyncio
async def test_finalize_creation_rolls_back_partial_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = uuid.uuid4()
    binding = ResearchBinding(session_id="session-1", source_ids=["source-1"])
    pitch = CreationPitch(
        premise="A translator finds a coded confession.",
        theme="Truth has a cost",
        logline="One confession changes everything.",
        synopsis="A translator follows the confession to its hidden author.",
        research_binding=binding,
    )
    project = NovelProject(
        id=project_id,
        title="Draft book",
        genre="mystery",
        status=ProjectStatus.DRAFT,
        extra_metadata={
            "research": {
                "session_id": "session-1",
                "status": "completed",
                "stages": [{"id": str(index), "status": "done"} for index in range(5)],
                "sources": [{"id": "source-1"}],
                "artifacts": [
                    {"id": "profile", "content": {"style_guide": "tense"}},
                    {
                        "id": "framework_proposal",
                        "content": {
                            "status": "pending_confirmation",
                            "research_binding": binding.model_dump(mode="json"),
                            "creation_proposal": pitch.model_dump(mode="json"),
                            "proposal": {},
                        },
                    },
                ],
            }
        },
    )

    class FakeUow:
        def __init__(self) -> None:
            self.rollback_count = 0
            self.pending_story_bibles: list[StoryBible] = []

        async def rollback(self) -> None:
            self.rollback_count += 1
            self.pending_story_bibles.clear()

    class FakeStoryBibles:
        def __init__(self, uow: FakeUow) -> None:
            self.uow = uow

        async def upsert(self, story: StoryBible, *, commit: bool = True) -> StoryBible:
            self.uow.pending_story_bibles.append(story)
            return story

    class FakeEngine:
        def __init__(self) -> None:
            self.uow = FakeUow()
            self.story_bibles = FakeStoryBibles(self.uow)

        async def get_project(self, _project_id):
            return project

        async def list_projects(self):
            return []

    engine = FakeEngine()

    async def fail_after_partial_write(*_args, **_kwargs):
        await engine.story_bibles.upsert(
            StoryBible(
                project_id=project_id,
                premise="partial",
                theme="partial",
                tone="tense",
                narrative_style="close third",
                target_word_count=80_000,
                chapter_word_count=2_000,
            ),
            commit=False,
        )
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(research_routes, "_apply_framework_proposal", fail_after_partial_write)
    body = ProjectFinalizeCreation(
        title="Final title",
        genre="mystery",
        pitch=pitch,
        research_binding=binding,
        framework_proposal={},
        framework_confirmed=True,
        confirmed_by="test-user",
    )

    with pytest.raises(RuntimeError, match="simulated write failure"):
        await research_routes.finalize_creation(project_id, body, engine)

    assert engine.uow.rollback_count == 1
    assert engine.uow.pending_story_bibles == []


def test_finalize_creation_rolls_back_real_postgresql_commit_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flush real writes to PostgreSQL, fail commit, and verify rollback."""
    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post("/projects", json={"title": f"Rollback {uuid.uuid4().hex[:8]}"})
        assert created.status_code == 201
        project_id = uuid.UUID(created.json()["id"])
        binding = {"session_id": "real-session", "source_ids": ["real-source"], "profile_artifact_id": "profile", "profile_version": 1}
        pitch = {
            "premise": "A translator finds a coded confession.",
            "theme": "Truth has a cost",
            "logline": "One confession changes everything.",
            "synopsis": "A translator follows the confession to its hidden author.",
            "reading_tags": [],
            "content_tags": [],
            "protagonist_names": [],
            "research_binding": binding,
        }

        async def seed_research() -> None:
            factory = get_session_factory(get_settings())
            async with factory() as session:
                row = await session.get(NovelProjectRow, project_id)
                assert row is not None
                row.extra_metadata = {
                    **(row.extra_metadata or {}),
                    "research": {
                        "session_id": "real-session",
                        "status": "completed",
                        "stages": [{"id": str(index), "status": "done"} for index in range(5)],
                        "sources": [{"id": "real-source"}],
                        "artifacts": [
                            {"id": "profile", "content": {"style_guide": "tense"}},
                            {
                                "id": "framework_proposal",
                                "content": {
                                    "status": "pending_confirmation",
                                    "research_binding": binding,
                                    "creation_proposal": pitch,
                                    "proposal": {},
                                },
                            },
                        ],
                    },
                }
                await session.commit()

        asyncio.run(seed_research())

        async def write_before_commit_failure(_project_id, _confirmation, engine, **_kwargs):
            await engine.story_bibles.upsert(
                StoryBible(
                    project_id=project_id,
                    premise="partial",
                    theme="partial",
                    tone="tense",
                    narrative_style="close third",
                    target_word_count=80_000,
                    chapter_word_count=2_000,
                ),
                commit=False,
            )
            return None

        async def fail_commit(_self):
            raise OperationalError(
                "simulated PostgreSQL commit failure",
                {},
                RuntimeError("connection dropped during commit"),
            )

        try:
            monkeypatch.setattr(research_routes, "_apply_framework_proposal", write_before_commit_failure)
            monkeypatch.setattr(SqlAlchemyUnitOfWork, "commit", fail_commit)
            response = client.post(
                f"/projects/{project_id}/finalize-creation",
                json={
                    "title": "Final title",
                    "genre": "mystery",
                    "language": "en",
                    "target_platform": "alphanovel",
                    "chapter_count_target": 120,
                    "target_reader": "female",
                    "pitch": pitch,
                    "research_binding": binding,
                    "framework_proposal": {},
                    "framework_confirmed": True,
                    "confirmed_by": "test-user",
                },
            )
            assert response.status_code == 500

            project = client.get(f"/projects/{project_id}")
            assert project.status_code == 200
            assert project.json()["status"] == "draft"
            assert client.get(f"/projects/{project_id}/story").status_code == 404
        finally:
            # The commit failure is deliberately global to this test. Restore it
            # before deleting the setup project, otherwise cleanup also fails.
            monkeypatch.undo()
            cleanup = client.delete(f"/projects/{project_id}")
            assert cleanup.status_code == 204

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.api.deps import get_llm_provider, get_review_workflow
from app.main import app
from tests.fakes import ScriptedJsonProvider, approve_payloads, editor_payload, generate_payloads
from novel_engine.workflows.agent_workflow import AgentWorkflow

CHARACTER = {
    "name": "Aria",
    "role": "protagonist",
    "personality": "proud",
    "background": "exiled bloodline",
    "goal": "reclaim dignity",
    "motivation": "never disposable",
    "fear": "the bond still owns her",
    "secret": "royal blood",
    "strength": "will",
    "weakness": "pride",
    "internal_conflict": "love vs revenge",
    "external_conflict": "Kael and the council",
    "speech_style": "clipped",
    "character_arc": "omega to sovereign",
    "tropes": ["rejected_mate"],
}

STORY = {
    "premise": "Rejected mate returns as hidden royalty.",
    "theme": "Power after humiliation",
    "tone": "dark romantic",
    "narrative_style": "close third serial",
    "logline": "She was rejected. The pack will remember.",
    "synopsis": "Aria is rejected and returns.",
    "target_word_count": 80000,
    "chapter_word_count": 1800,
}

PLAN = {
    "chapter_number": 1,
    "chapter_title": "The Rejection",
    "pov": "Aria",
    "location": "Moonridge Pack Hall",
    "characters": ["Aria"],
    "chapter_goal": "public rejection",
    "conflict": "Kael chooses another",
    "emotional_arc": "humiliation to ice",
    "new_information": "council knew",
    "reveal": "she does not beg",
    "foreshadowing": "crest burns",
    "setup": "ceremony",
    "payoff": "she walks out",
    "cliffhanger": "a stranger says princess",
    "scenes": [
        {
            "scene_number": 1,
            "location": "dais",
            "characters": ["Aria"],
            "goal": "leave unbroken",
            "conflict": "pack watches",
            "turning_point": "she laughs",
            "dialogue_goal": "one cutting line",
            "emotion": "ice",
            "information_revealed": "she expected it",
            "ending": "she crosses the torches",
        }
    ],
}


def _client() -> TestClient:
    return TestClient(app)


def test_request_id_and_me() -> None:
    with _client() as client:
        response = client.get("/me", headers={"X-Request-ID": "req-test-1", "X-Actor": "editor"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "req-test-1"
        body = response.json()
        assert body["id"] == "editor"
        assert body["is_authenticated"] is True
        assert body["auth"] == "reserved"


def test_unified_error_format() -> None:
    with _client() as client:
        response = client.get(f"/projects/{uuid.uuid4()}")
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == "not_found"
        assert "request_id" in payload["error"]
        assert "X-Request-ID" in response.headers


def test_create_project_persists_generated_reader_pitch() -> None:
    with _client() as client:
        marker = uuid.uuid4().hex[:8]
        created = client.post(
            "/projects",
            json={
                "title": f"Pitch {marker}",
                "genre": "mystery",
                "premise": "A translator discovers a coded confession.",
                "theme": "Truth has a cost",
                "logline": "One confession turns a quiet town into a crime scene.",
                "synopsis": "A translator deciphers a confession and realizes the killer is still nearby.",
            },
        )
        assert created.status_code == 201
        project_id = created.json()["id"]
        try:
            story = client.get(f"/projects/{project_id}/story")
            assert story.status_code == 200
            assert story.json()["theme"] == "Truth has a cost"
            assert story.json()["synopsis"].startswith("A translator deciphers")
        finally:
            client.delete(f"/projects/{project_id}")


def test_planning_hitl_and_pipeline_advance() -> None:
    with _client() as client:
        marker = uuid.uuid4().hex[:8]
        created = client.post(
            "/projects",
            json={"title": f"HITL {marker}", "tropes": ["rejected_mate"], "target_platform": "alphanovel"},
            headers={"X-Actor": "editor"},
        )
        assert created.status_code == 201
        project_id = created.json()["id"]
        try:
            assert created.json()["current_stage"] == "idea"
            advanced = client.post(
                f"/projects/{project_id}/pipeline/advance",
                json={"confirmed_by": "editor"},
                headers={"X-Actor": "editor"},
            )
            assert advanced.status_code == 200
            assert advanced.json()["current_stage"] == "story_bible"

            story = client.patch(f"/projects/{project_id}/story", json=STORY, headers={"X-Actor": "editor"})
            assert story.status_code == 200
            assert client.post(f"/projects/{project_id}/story/submit", headers={"X-Actor": "editor"}).status_code == 200
            approved = client.post(
                f"/projects/{project_id}/story/approve",
                json={"confirmed_by": "editor"},
                headers={"X-Actor": "editor"},
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "approved"

            to_world = client.post(
                f"/projects/{project_id}/pipeline/advance",
                json={},
                headers={"X-Actor": "editor"},
            )
            assert to_world.status_code == 200
            assert to_world.json()["current_stage"] == "world_bible"
        finally:
            client.delete(f"/projects/{project_id}")


def test_project_story_character_world_plot_arc_chapter_memory_settings() -> None:
    with _client() as client:
        marker = uuid.uuid4().hex[:8]
        created = client.post(
            "/projects",
            json={
                "title": f"Rejected Luna {marker}",
                "tropes": ["rejected_mate"],
                "target_platform": "alphanovel",
                "premise": "A rejected heroine returns under a hidden identity.",
                "theme": "Identity after betrayal",
                "logline": "They cast her out before learning who she was.",
                "synopsis": "After exile, she returns with a secret that can change the pack.",
            },
        )
        assert created.status_code == 201
        project_id = created.json()["id"]
        try:
            listed = client.get("/projects")
            assert listed.status_code == 200
            assert any(item["id"] == project_id for item in listed.json())
            generated_story = client.get(f"/projects/{project_id}/story")
            assert generated_story.status_code == 200
            assert generated_story.json()["synopsis"].startswith("After exile")

            patched = client.patch(f"/projects/{project_id}", json={"title": f"Rejected Luna {marker} v2"})
            assert patched.status_code == 200
            assert patched.json()["title"].endswith("v2")

            story = client.patch(f"/projects/{project_id}/story", json=STORY)
            assert story.status_code == 200
            assert client.get(f"/projects/{project_id}/story").json()["premise"].startswith("Rejected")

            character = client.post(f"/projects/{project_id}/characters", json=CHARACTER)
            assert character.status_code == 201
            character_id = character.json()["id"]
            assert client.get(f"/projects/{project_id}/characters").json()[0]["name"] == "Aria"
            updated = client.patch(
                f"/projects/{project_id}/characters/{character_id}",
                json={"rank": "omega"},
            )
            assert updated.status_code == 200
            assert updated.json()["rank"] == "omega"

            world = client.patch(
                f"/projects/{project_id}/world",
                json={
                    "name": "Moonridge",
                    "summary": "A mountain pack under an Alpha King.",
                    "geography": "Blackpine Forest",
                    "factions": ["Moonridge Pack"],
                    "rules": [
                        {
                            "name": "Public rejection",
                            "category": "mate_bond",
                            "description": "A public rejection severs Luna rank.",
                            "is_hard_constraint": True,
                        }
                    ],
                },
            )
            assert world.status_code == 200
            assert client.get(f"/projects/{project_id}/world").json()["rules"][0]["name"] == "Public rejection"

            plot = client.patch(
                f"/projects/{project_id}/plot",
                json={
                    "title": "Rejected Luna",
                    "summary": "Rejection, exile, return.",
                    "beats": [
                        {"name": "Rejection", "description": "Pack Hall"},
                        {"name": "Exile", "description": "Forest"},
                        {"name": "Return", "description": "Challenge"},
                    ],
                },
            )
            assert plot.status_code == 200
            assert client.get(f"/projects/{project_id}/plot").json()["title"] == "Rejected Luna"

            arc = client.post(
                f"/projects/{project_id}/arcs",
                json={"title": "Rejection Arc", "sequence": 1, "summary": "Public rejection and exile."},
            )
            assert arc.status_code == 201
            arc_id = arc.json()["id"]
            assert client.get(f"/projects/{project_id}/arcs").status_code == 200
            patched_arc = client.patch(
                f"/projects/{project_id}/arcs/{arc_id}",
                json={"summary": "Public rejection, then the gates."},
            )
            assert patched_arc.status_code == 200

            plan = client.post(f"/projects/{project_id}/chapters/plan", json=PLAN)
            assert plan.status_code == 201
            assert client.post(f"/projects/{project_id}/chapters/1/plan/submit").status_code == 200
            assert client.post(
                f"/projects/{project_id}/chapters/1/plan/approve",
                json={"confirmed_by": "writer"},
            ).status_code == 200
            chapters = client.get(f"/projects/{project_id}/chapters")
            assert chapters.status_code == 200
            assert chapters.json()[0]["chapter_number"] == 1

            app.dependency_overrides[get_llm_provider] = lambda: ScriptedJsonProvider(generate_payloads())
            generated = client.post(
                f"/projects/{project_id}/chapters/1/generate",
                json={"human_notes": "Keep the rejection public.", "persist": True},
                headers={"X-Actor": "writer"},
            )
            assert generated.status_code == 200, generated.text
            assert "rejected Aria" in generated.json()["chapter"]["content"]

            app.dependency_overrides[get_llm_provider] = lambda: ScriptedJsonProvider(
                [editor_payload(), {"overall": "PASS", "findings": []}]
            )
            app.dependency_overrides[get_review_workflow] = lambda: AgentWorkflow(
                ScriptedJsonProvider(
                    [
                        {
                            "reader_pressure_score": 8,
                            "reader_promise_score": 8,
                            "rhythm_score": 8,
                            "ai_style_risk_score": 8,
                            "needs_human_review": False,
                            "findings": [],
                            "repair_priorities": [],
                        },
                        {"overall": "PASS", "findings": []},
                    ]
                )
            )
            reviewed = client.post(f"/projects/{project_id}/chapters/1/review")
            assert reviewed.status_code == 200
            assert reviewed.json()["chapter"]["status"] == "reviewed", reviewed.text

            app.dependency_overrides[get_llm_provider] = lambda: ScriptedJsonProvider(
                [{"overall": "WARNING", "findings": []}]
            )
            continuity = client.post(f"/projects/{project_id}/chapters/1/continuity")
            assert continuity.status_code == 200
            assert continuity.json()["continuity"]["overall"] == "WARNING"

            app.dependency_overrides[get_llm_provider] = lambda: ScriptedJsonProvider(approve_payloads())
            approved = client.post(
                f"/projects/{project_id}/chapters/1/approve",
                json={"confirmed_by": "editor"},
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "approved"
            detail = client.get(f"/projects/{project_id}/chapters/1")
            assert detail.status_code == 200
            assert detail.json()["plan"]["chapter_title"] == "The Rejection"

            assert client.get(f"/projects/{project_id}/memory").status_code == 200
            assert client.get(f"/projects/{project_id}/timeline").status_code == 200
            hooks = client.get(f"/projects/{project_id}/hooks")
            assert hooks.status_code == 200
            assert any("princess" in item["description"] for item in hooks.json())
            assert client.get(f"/projects/{project_id}/foreshadowing").status_code == 200

            llm = client.patch(
                f"/projects/{project_id}/settings/llm",
                json={"provider": "openai_compatible", "model": "gpt-4o-mini", "temperature": 0.4},
            )
            assert llm.status_code == 200
            fetched = client.get(f"/projects/{project_id}/settings/llm")
            assert fetched.json()["model"] == "gpt-4o-mini"

            client.patch(f"/projects/{project_id}/chapters/1", json={"title": "Pack Hall"})
            extra = client.post(
                f"/projects/{project_id}/characters",
                json={**CHARACTER, "name": "Kael", "role": "love_interest"},
            )
            assert extra.status_code == 201
            deleted_extra = client.delete(f"/projects/{project_id}/characters/{extra.json()['id']}")
            assert deleted_extra.status_code == 422, deleted_extra.text
            assert client.delete(f"/projects/{project_id}/arcs/{arc_id}").status_code == 422
        finally:
            app.dependency_overrides.clear()
            client.delete(f"/projects/{project_id}")

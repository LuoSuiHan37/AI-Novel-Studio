from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session", autouse=True)
def _prompts_dir() -> None:
    os.environ.setdefault("NOVEL_ENGINE_PROMPTS_DIR", str(ROOT / "prompts"))
    os.environ.setdefault(
        "NOVEL_ENGINE_AGENT_PROMPTS_DIR",
        str(Path(__file__).resolve().parents[1] / "prompts"),
    )
    os.environ.setdefault(
        "NOVEL_ENGINE_PRESETS_DIR",
        str(Path(__file__).resolve().parents[1] / "presets"),
    )

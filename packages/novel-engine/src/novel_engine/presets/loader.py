from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

from novel_engine.presets.models import NovelPreset, PlatformPreset, StyleBundle


def presets_root() -> Path:
    env_dir = os.environ.get("NOVEL_ENGINE_PRESETS_DIR")
    if env_dir:
        return Path(env_dir)
    package_presets = Path(__file__).resolve().parents[3] / "presets"
    if package_presets.is_dir():
        return package_presets
    raise FileNotFoundError(
        "Preset directory not found. Set NOVEL_ENGINE_PRESETS_DIR "
        "or keep packages/novel-engine/presets on disk."
    )


@lru_cache(maxsize=32)
def load_platform_preset(preset_id: str) -> PlatformPreset:
    path = presets_root() / "platforms" / f"{preset_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"Unknown platform preset '{preset_id}'. Add a preset under "
            f"{presets_root() / 'platforms'} instead of silently using another platform's rules."
        )
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PlatformPreset.model_validate(payload)


@lru_cache(maxsize=32)
def load_novel_preset(preset_id: str) -> NovelPreset:
    slug = (preset_id or "werewolf_romance").replace(" ", "_").lower()
    path = presets_root() / "novels" / f"{slug}.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"Unknown novel preset '{preset_id}'. Add a preset under "
            f"{presets_root() / 'novels'} instead of silently using werewolf romance rules."
        )
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return NovelPreset.model_validate(payload)


def resolve_style_bundle(
    *, platform_id: str | None, novel_id: str | None, language: str | None = None
) -> StyleBundle:
    novel = load_novel_preset(novel_id or "werewolf_romance")
    inferred_platform = "fanqie" if (language or "").lower() in {"zh", "zh-cn"} else ""
    platform = load_platform_preset(
        platform_id or inferred_platform or novel.default_platform or "alphanovel"
    )
    return StyleBundle(platform=platform, novel=novel)

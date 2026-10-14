from __future__ import annotations

from novel_engine.domain.errors import KnowledgeLeakError
from novel_engine.memory.models import ContextPackage, MemoryRecord
from novel_engine.models.enums import EpistemicStatus


def secret_records(records: list[MemoryRecord]) -> list[MemoryRecord]:
    return [item for item in records if item.epistemic_status is EpistemicStatus.SECRET]


def forbidden_for_character(records: list[MemoryRecord], name: str) -> list[str]:
    secrets: list[str] = []
    for item in secret_records(records):
        if name in item.unknown_to or (item.known_by and name not in item.known_by):
            secrets.append(item.content)
    return secrets


def build_forbidden_map(records: list[MemoryRecord], names: list[str]) -> dict[str, list[str]]:
    return {name: forbidden_for_character(records, name) for name in names}


def check_prose_for_pov(prose: str, pov: str, forbidden: list[str]) -> None:
    lowered = prose.lower()
    for secret in forbidden:
        if secret.lower() in lowered:
            raise KnowledgeLeakError(f"{pov} must not know secret: {secret}")


def check_prose_knowledge(prose: str, pov: str, package: ContextPackage) -> None:
    check_prose_for_pov(prose, pov, package.forbidden_knowledge.get(pov, []))


def filter_records_for_pov(records: list[MemoryRecord], pov: str) -> list[MemoryRecord]:
    allowed: list[MemoryRecord] = []
    for item in records:
        if item.epistemic_status is EpistemicStatus.SECRET:
            if pov in item.unknown_to:
                continue
            if item.known_by and pov not in item.known_by:
                continue
        allowed.append(item)
    return allowed

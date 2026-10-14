from __future__ import annotations

import uuid

from novel_engine.domain.errors import InvalidStateError
from novel_engine.memory.models import MemoryProposal, MemoryRecord
from novel_engine.models.enums import EpistemicStatus, MemoryLayer


class MemoryWritePolicy:
    """LLM output is never auto-promoted to confirmed long-term canon."""

    CHARACTER_ONLY = {EpistemicStatus.CHARACTER_BELIEF, EpistemicStatus.RUMOR}


def apply_write_policy(
    proposal: MemoryProposal,
    project_id: uuid.UUID,
    *,
    confirmed_by: str | None = None,
) -> MemoryRecord:
    if not proposal.content.strip():
        raise InvalidStateError("memory content is empty")
    status = proposal.suggested_status
    source = proposal.source
    if source == "llm" and not confirmed_by:
        if status is EpistemicStatus.CONFIRMED_FACT:
            status = EpistemicStatus.TENTATIVE_FACT
        if proposal.layer is MemoryLayer.GLOBAL and status is not EpistemicStatus.SECRET:
            raise InvalidStateError(
                "LLM cannot write global canon; confirm the fact with confirmed_by first"
            )
    if status is EpistemicStatus.CONFIRMED_FACT and not confirmed_by:
        raise InvalidStateError("confirmed_fact requires confirmed_by")
    if proposal.layer is MemoryLayer.GLOBAL and status in MemoryWritePolicy.CHARACTER_ONLY:
        raise InvalidStateError("rumors and beliefs cannot enter global memory")
    if status is EpistemicStatus.SECRET and not proposal.known_by and not proposal.unknown_to:
        raise InvalidStateError("secrets must declare known_by or unknown_to")
    return MemoryRecord(
        project_id=project_id,
        layer=proposal.layer,
        epistemic_status=status,
        memory_type=proposal.memory_type,
        importance=proposal.importance,
        content=proposal.content.strip(),
        chapter_number=proposal.chapter_number,
        character_name=proposal.character_name,
        location=proposal.location,
        known_by=list(proposal.known_by),
        unknown_to=list(proposal.unknown_to),
        tags=list(proposal.tags),
        source=source,
        confirmed_by=confirmed_by,
    )

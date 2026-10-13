from __future__ import annotations

from novel_engine.domain.errors import InvalidStateError
from novel_engine.models.entities import DomainModel, touch
from novel_engine.models.enums import ApprovalStatus


def submit_for_review(entity: DomainModel) -> None:
    status = getattr(entity, "status")
    if status is ApprovalStatus.APPROVED:
        raise InvalidStateError("approved records must be edited into draft before re-review")
    setattr(entity, "status", ApprovalStatus.PENDING_REVIEW)
    touch(entity)


def approve(entity: DomainModel) -> None:
    status = getattr(entity, "status")
    if status is not ApprovalStatus.PENDING_REVIEW:
        raise InvalidStateError("only pending_review records can be approved (human confirmation required)")
    setattr(entity, "status", ApprovalStatus.APPROVED)
    touch(entity)


def reject(entity: DomainModel) -> None:
    status = getattr(entity, "status")
    if status is not ApprovalStatus.PENDING_REVIEW:
        raise InvalidStateError("only pending_review records can be rejected")
    setattr(entity, "status", ApprovalStatus.REJECTED)
    touch(entity)


def reopen_for_edit(entity: DomainModel) -> None:
    setattr(entity, "status", ApprovalStatus.DRAFT)
    touch(entity)


def require_approved(entity: DomainModel, *, label: str) -> None:
    if getattr(entity, "status") is not ApprovalStatus.APPROVED:
        raise InvalidStateError(f"{label} must be approved before this step")

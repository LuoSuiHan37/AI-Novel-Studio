from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from novel_engine.models.enums import ContinuityVerdict


class StoryEntityState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    entity_type: str = "character"
    status: str = "active"  # active / absent / dead / destroyed / retired
    current_location: str = ""
    owner: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    introduced_chapter: int | None = None
    last_seen_chapter: int | None = None
    source_evidence: str = ""


class StoryResourceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: float
    unit: str = ""
    location: str = ""
    owner: str = ""
    condition: str = ""
    source_evidence: str = ""


class StoryRelationshipState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    relation: str
    object: str
    status: str = "active"
    source_evidence: str = ""


class StoryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    chapter_number: int = 0
    entities: list[StoryEntityState] = Field(default_factory=list)
    resources: list[StoryResourceState] = Field(default_factory=list)
    relationships: list[StoryRelationshipState] = Field(default_factory=list)

    def entity(self, name: str) -> StoryEntityState | None:
        needle = name.casefold().strip()
        return next(
            (
                item
                for item in self.entities
                if item.canonical_name.casefold() == needle
                or needle in {alias.casefold() for alias in item.aliases}
            ),
            None,
        )


class EntityStateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_name: str
    action: str  # create / update / leave / die / destroy / rename
    entity_type: str = "character"
    aliases: list[str] = Field(default_factory=list)
    status: str | None = None
    current_location: str | None = None
    owner: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    replacement_name: str | None = None
    evidence: str


class ResourceStateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    action: str  # set / add / consume / transfer
    quantity: float
    unit: str = ""
    location: str | None = None
    owner: str | None = None
    condition: str | None = None
    evidence: str


class StoryStateDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[EntityStateChange] = Field(default_factory=list)
    resources: list[ResourceStateChange] = Field(default_factory=list)
    relationships: list[StoryRelationshipState] = Field(default_factory=list)
    observed_entities: list[str] = Field(default_factory=list)


class StoryStateFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: ContinuityVerdict
    category: str
    problem: str
    evidence: str
    recommendation: str


def apply_state_delta(
    state: StoryState,
    delta: StoryStateDelta,
    *,
    chapter_number: int,
) -> tuple[StoryState, list[StoryStateFinding]]:
    """Apply an LLM-proposed delta with deterministic safety checks."""
    next_state = state.model_copy(deep=True, update={"chapter_number": chapter_number})
    findings: list[StoryStateFinding] = []

    for change in delta.entities:
        current = next_state.entity(change.canonical_name)
        if change.action == "create":
            if current is not None:
                findings.append(_finding("duplicate_entity_create", "ERROR", f"实体“{change.canonical_name}”已存在。", change.evidence))
                continue
            next_state.entities.append(
                StoryEntityState(
                    canonical_name=change.canonical_name,
                    aliases=change.aliases,
                    entity_type=change.entity_type,
                    status=change.status or "active",
                    current_location=change.current_location or "",
                    owner=change.owner or "",
                    attributes=change.attributes,
                    introduced_chapter=chapter_number,
                    last_seen_chapter=chapter_number,
                    source_evidence=change.evidence,
                )
            )
            continue

        if current is None:
            findings.append(_finding("unknown_entity_update", "ERROR", f"实体“{change.canonical_name}”尚未建立，不能执行 {change.action}。", change.evidence))
            continue
        if current.status in {"dead", "destroyed", "retired"} and change.action not in {"rename"}:
            findings.append(_finding("terminal_entity_reappeared", "ERROR", f"已处于终止状态的实体“{current.canonical_name}”再次发生状态变化。", change.evidence))
            continue
        if not change.evidence.strip():
            findings.append(_finding("state_change_without_evidence", "ERROR", f"实体“{change.canonical_name}”的状态变化没有正文证据。", ""))
            continue
        status_by_action = {
            "leave": "absent",
            "die": "dead",
            "destroy": "destroyed",
        }
        if change.status or change.action in status_by_action:
            current.status = change.status or status_by_action[change.action]
        if change.current_location is not None:
            current.current_location = change.current_location
        if change.owner is not None:
            current.owner = change.owner
        if change.aliases:
            current.aliases = list(dict.fromkeys([*current.aliases, *change.aliases]))
        current.attributes.update(change.attributes)
        current.last_seen_chapter = chapter_number
        current.source_evidence = change.evidence

    for change in delta.resources:
        resource = next((item for item in next_state.resources if item.name.casefold() == change.name.casefold()), None)
        if change.action == "set":
            if resource is None:
                resource = StoryResourceState(name=change.name, quantity=change.quantity, unit=change.unit, source_evidence=change.evidence)
                next_state.resources.append(resource)
            else:
                resource.quantity = change.quantity
        elif resource is None:
            findings.append(_finding("unknown_resource_update", "ERROR", f"资源“{change.name}”尚未建立，不能执行 {change.action}。", change.evidence))
            continue
        elif change.action in {"add", "consume"}:
            amount = change.quantity if change.action == "add" else -change.quantity
            if resource.quantity + amount < 0:
                findings.append(_finding("resource_negative", "ERROR", f"资源“{change.name}”数量不能小于零。", change.evidence))
                continue
            resource.quantity += amount
        elif change.action == "transfer":
            if resource.quantity < change.quantity:
                findings.append(_finding("resource_transfer_overflow", "ERROR", f"资源“{change.name}”转移数量超过库存。", change.evidence))
                continue
            resource.quantity -= change.quantity
        if resource is not None:
            resource.unit = change.unit or resource.unit
            resource.location = change.location if change.location is not None else resource.location
            resource.owner = change.owner if change.owner is not None else resource.owner
            resource.condition = change.condition if change.condition is not None else resource.condition
            resource.source_evidence = change.evidence

    for relationship in delta.relationships:
        next_state.relationships = [
            item for item in next_state.relationships
            if not (
                item.subject.casefold() == relationship.subject.casefold()
                and item.relation.casefold() == relationship.relation.casefold()
                and item.object.casefold() == relationship.object.casefold()
            )
        ]
        next_state.relationships.append(relationship)

    observed = {item.casefold() for item in delta.observed_entities}
    if observed:
        for entity in next_state.entities:
            if entity.status == "active" and entity.canonical_name.casefold() not in observed:
                findings.append(_finding("active_entity_not_observed", "WARNING", f"活跃实体“{entity.canonical_name}”本章没有被明确观察到，需确认是暂时离场还是遗漏。", f"observed_entities={sorted(observed)}"))
    return next_state, findings


def _finding(category: str, severity: str, problem: str, evidence: str) -> StoryStateFinding:
    return StoryStateFinding(
        severity=ContinuityVerdict.ERROR if severity == "ERROR" else ContinuityVerdict.WARNING,
        category=category,
        problem=problem,
        evidence=evidence or category,
        recommendation="补充正文中的状态变化或明确说明实体、资源的去向。",
    )

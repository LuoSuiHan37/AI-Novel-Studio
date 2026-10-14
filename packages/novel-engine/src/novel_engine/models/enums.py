"""Domain enumerations shared by persistence and (later) application services."""

from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    PLANNING = "planning"
    WRITING = "writing"
    REVISING = "revising"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class PipelineStage(StrEnum):
    """Human-in-the-loop stages. The next stage must not start until the current one is confirmed."""

    IDEA = "idea"
    STORY_BIBLE = "story_bible"
    WORLD_BIBLE = "world_bible"
    CHARACTERS = "characters"
    MASTER_PLOT = "master_plot"
    CHAPTER_PLAN = "chapter_plan"
    DRAFTING = "drafting"
    REVIEW = "review"
    PUBLISH = "publish"


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChapterStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    PUBLISHED = "published"


class CharacterRole(StrEnum):
    PROTAGONIST = "protagonist"
    LOVE_INTEREST = "love_interest"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    EXTRA = "extra"


class EpistemicStatus(StrEnum):
    CONFIRMED_FACT = "confirmed_fact"
    TENTATIVE_FACT = "tentative_fact"
    CHARACTER_BELIEF = "character_belief"
    RUMOR = "rumor"
    SECRET = "secret"


class MemoryLayer(StrEnum):
    GLOBAL = "global"
    CHARACTER = "character"
    TIMELINE = "timeline"
    CHAPTER = "chapter"
    VECTOR = "vector"


class MemoryType(StrEnum):
    FACT = "fact"
    EVENT = "event"
    CHARACTER = "character"
    RELATIONSHIP = "relationship"
    WORLD_RULE = "world_rule"
    SECRET = "secret"
    HOOK = "hook"
    EMOTION = "emotion"
    PLOT = "plot"


class Importance(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HookType(StrEnum):
    CLIFFHANGER = "cliffhanger"
    QUESTION = "question"
    SECRET = "secret"
    ROMANCE = "romance"
    DANGER = "danger"
    REVELATION = "revelation"
    DELAYED_PAYOFF = "delayed_payoff"


class HookStatus(StrEnum):
    PLANNED = "planned"
    PLANTED = "planted"
    ACTIVE = "active"
    RESOLVED = "resolved"
    DROPPED = "dropped"


class ForeshadowStatus(StrEnum):
    PLANNED = "planned"
    PLANTED = "planted"
    PAID_OFF = "paid_off"
    MISSED = "missed"
    DROPPED = "dropped"


class ContinuityIssueStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class ContinuitySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GROK = "grok"
    OPENAI_COMPATIBLE = "openai_compatible"


class ContinuityVerdict(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class IntensityLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXPLICIT = "explicit"


class PointOfView(StrEnum):
    FIRST = "first"
    THIRD_LIMITED = "third_limited"
    THIRD_OMNISCIENT = "third_omniscient"
    MULTIPLE = "multiple"


class NarrativeTense(StrEnum):
    PAST = "past"
    PRESENT = "present"


class RomanceTrope(StrEnum):
    REJECTED_MATE = "rejected_mate"
    FATED_MATE = "fated_mate"
    SECOND_CHANCE_MATE = "second_chance_mate"
    SECRET_BABY = "secret_baby"
    PREGNANT_AND_REJECTED = "pregnant_and_rejected"
    ALPHA_KING = "alpha_king"
    POWERFUL_FEMALE_LEAD = "powerful_female_lead"
    HIDDEN_IDENTITY = "hidden_identity"
    REVENGE = "revenge"
    FORCED_MARRIAGE = "forced_marriage"
    ENEMIES_TO_LOVERS = "enemies_to_lovers"

"""Domain-layer failures. Independent of HTTP and SQLAlchemy."""


class DomainError(Exception):
    """Base class for novel-engine business rule violations."""


class NotFoundError(DomainError):
    pass


class DuplicateError(DomainError):
    pass


class InvalidStateError(DomainError):
    pass


class ApprovalRequiredError(DomainError):
    """Human-in-the-loop gate: the caller must confirm before continuing."""


class KnowledgeLeakError(DomainError):
    """A character is shown knowing a secret that is not in their knowledge set."""

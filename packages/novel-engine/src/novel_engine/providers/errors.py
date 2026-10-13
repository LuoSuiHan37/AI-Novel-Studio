"""LLM provider exceptions. Do not leak API keys in messages."""


class ProviderError(Exception):
    """Base error for all LLM provider failures."""


class ProviderAuthError(ProviderError):
    """Missing, invalid, or unauthorized API credentials."""


class ProviderRateLimitError(ProviderError):
    """Provider returned HTTP 429 or equivalent rate-limit payload."""


class ProviderTimeoutError(ProviderError):
    """Request exceeded the configured timeout."""


class ProviderInvalidResponseError(ProviderError):
    """Payload could not be parsed, validated, or did not match the contract."""


class ProviderRequestError(ProviderError):
    """The provider request failed before a usable model response was received."""


class ProviderUnsupportedError(ProviderError):
    """The selected provider/model does not support the requested operation."""

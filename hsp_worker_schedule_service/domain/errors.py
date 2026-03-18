class DomainError(Exception):
    """Base domain error."""


class ValidationError(DomainError):
    """Raised when input validation fails."""


class NotFoundError(DomainError):
    """Raised when entity does not exist."""

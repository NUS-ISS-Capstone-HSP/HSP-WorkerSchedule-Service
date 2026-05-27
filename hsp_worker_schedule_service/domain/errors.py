class DomainError(Exception):
    """Base domain error."""


class ValidationError(DomainError):
    """Raised when input validation fails."""


class NotFoundError(DomainError):
    """Raised when entity does not exist."""


class ConflictError(DomainError):
    """Raised when operation conflicts with current state."""


class UnauthorizedError(DomainError):
    """Raised when request metadata is missing or invalid."""

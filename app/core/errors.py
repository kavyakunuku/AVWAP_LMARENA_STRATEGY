from dataclasses import dataclass
from .enums import ErrorCategory, Severity

@dataclass(slots=True)
class AppError(Exception):
    category: ErrorCategory
    severity: Severity
    message: str
    retryable: bool = False
    action: str | None = None

    def __str__(self) -> str:
        return f"{self.category}: {self.message}"

class ConfigurationError(AppError):
    pass

class DhanApiError(AppError):
    pass

class ValidationFailure(AppError):
    pass

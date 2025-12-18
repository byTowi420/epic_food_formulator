"""Domain-specific exceptions.

Custom exceptions provide better error handling and clearer intent
than generic exceptions.
"""


class FoodFormulatorError(Exception):
    """Base exception for all application errors."""


# ============================================================================
# Domain Errors
# ============================================================================


class InvalidFormulationError(FoodFormulatorError):
    """Raised when formulation state is invalid."""


class IngredientNotFoundError(FoodFormulatorError):
    """Raised when an ingredient cannot be found."""


class InvalidIngredientError(FoodFormulatorError):
    """Raised when ingredient data is invalid."""


class InvalidNutrientDataError(FoodFormulatorError):
    """Raised when nutrient data is malformed or invalid."""


class CalculationError(FoodFormulatorError):
    """Raised when nutrient calculation fails."""


# ============================================================================
# Infrastructure Errors
# ============================================================================


class APIError(FoodFormulatorError):
    """Base exception for API-related errors."""


class USDAAPIError(APIError):
    """Generic error for USDA API issues."""


class USDAHTTPError(USDAAPIError):
    """HTTP error with status code context for fallback handling."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class APIKeyMissingError(USDAAPIError):
    """Raised when USDA API key is not configured."""


class APITimeoutError(USDAAPIError):
    """Raised when API request times out."""


class APIRateLimitError(USDAAPIError):
    """Raised when API rate limit is exceeded."""


# ============================================================================
# Persistence Errors
# ============================================================================


class PersistenceError(FoodFormulatorError):
    """Base exception for persistence-related errors."""


class FormulationNotFoundError(PersistenceError):
    """Raised when formulation file is not found."""


class InvalidFormulationFileError(PersistenceError):
    """Raised when formulation file is malformed."""


class ExportError(PersistenceError):
    """Raised when export operation fails."""

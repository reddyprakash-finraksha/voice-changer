"""
Custom exception hierarchy + FastAPI exception handlers.
Every error returned by the API follows one consistent JSON shape:
    { "error": { "code": "...", "message": "...", "details": {...} } }
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse


class VoiceStudioError(Exception):
    """Base class for all application-level errors."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ValidationError(VoiceStudioError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class AuthenticationError(VoiceStudioError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_error"


class AuthorizationError(VoiceStudioError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "authorization_error"


class NotFoundError(VoiceStudioError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConsentRequiredError(VoiceStudioError):
    """Raised when a user tries to clone/use a voice without recorded consent."""
    status_code = status.HTTP_403_FORBIDDEN
    code = "consent_required"


class RateLimitedError(VoiceStudioError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class UpstreamServiceError(VoiceStudioError):
    """Raised when an external provider (ElevenLabs, translation API, Supabase) fails."""
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_service_error"


def _error_payload(exc: VoiceStudioError) -> dict:
    return {"error": {"code": exc.code, "message": exc.message, "details": exc.details}}


async def voicestudio_exception_handler(request: Request, exc: VoiceStudioError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_error_payload(exc))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals (stack traces, secrets) to the client.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred.", "details": {}}},
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(VoiceStudioError, voicestudio_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

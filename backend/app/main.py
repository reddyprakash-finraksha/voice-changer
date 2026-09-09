"""
VoiceStudio API — application factory & entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000

Docs available at /docs (Swagger) and /redoc once running.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import auth, health, synthesize, translate, voice
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.ENV)

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description=(
            "Script -> translation -> authorized voice cloning -> emotional, "
            "tone/pitch/speed-controllable speech synthesis."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(voice.router, prefix=settings.API_V1_PREFIX)
    app.include_router(translate.router, prefix=settings.API_V1_PREFIX)
    app.include_router(synthesize.router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()

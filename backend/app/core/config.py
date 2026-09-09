"""
Centralized application configuration.
All secrets/config are loaded from environment variables (.env in dev,
real environment variables in production). Nothing is hardcoded.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "VoiceStudio API"
    ENV: str = Field(default="development")  # development | staging | production
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # --- Security / Auth ---
    JWT_SECRET_KEY: str = Field(..., description="Required. Generate with `openssl rand -hex 32`")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8501"]  # Streamlit dev default

    # --- Rate limiting ---
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_SYNTHESIZE: str = "10/minute"
    RATE_LIMIT_VOICE_ENROLL: str = "5/hour"

    # --- Text-to-Speech / Voice cloning provider (ElevenLabs) ---
    ELEVENLABS_API_KEY: str = Field(default="", description="Required for real TTS/voice cloning calls")
    ELEVENLABS_BASE_URL: str = "https://api.elevenlabs.io/v1"
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    ELEVENLABS_TIMEOUT_SECONDS: int = 60

    # --- Translation provider ---
    TRANSLATION_PROVIDER: str = "google_free"  # google_free | deepl | openai
    DEEPL_API_KEY: str = Field(default="")
    OPENAI_API_KEY: str = Field(default="")

    # --- Storage (Supabase) ---
    SUPABASE_URL: str = Field(default="")
    SUPABASE_SERVICE_KEY: str = Field(default="")
    SUPABASE_VOICE_BUCKET: str = "voice-samples"
    SUPABASE_AUDIO_BUCKET: str = "generated-audio"
    LOCAL_STORAGE_FALLBACK_DIR: str = "/tmp/voicestudio_storage"

    # --- Validation limits ---
    MAX_SCRIPT_CHARS: int = 5000
    MAX_VOICE_SAMPLE_MB: int = 15
    ALLOWED_VOICE_MIME_TYPES: List[str] = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/webm"]
    MIN_VOICE_SAMPLE_SECONDS: int = 30  # ElevenLabs recommends 1-3 minutes; we enforce a sane minimum

    # --- Supported languages (ISO 639-1) for translation + synthesis ---
    SUPPORTED_LANGUAGES: List[str] = [
        "en", "hi", "ta", "te", "kn", "ml", "bn", "mr", "gu", "pa",
        "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ar", "ru",
    ]


@lru_cache
def get_settings() -> "Settings":
    return Settings()

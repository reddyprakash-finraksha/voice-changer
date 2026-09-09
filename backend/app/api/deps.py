"""
Shared FastAPI dependencies: current-user extraction, service singletons.
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.models.user import UserRecord, UserRepository, get_user_repository
from app.services.storage_service import StorageBackend, get_storage_backend
from app.services.tts_service import TTSProvider, get_tts_provider
from app.services.translation_service import TranslationService
from app.services.voice_service import VoiceRepository, VoiceService, get_voice_repository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    users: UserRepository = Depends(get_user_repository),
) -> UserRecord:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    user = users.get_by_id(user_id) if user_id else None
    if user is None:
        raise AuthenticationError("User not found for the supplied token.")
    return user


def get_tts_provider_dep() -> TTSProvider:
    return get_tts_provider()


def get_storage_dep() -> StorageBackend:
    return get_storage_backend()


def get_translation_service_dep() -> TranslationService:
    return TranslationService()


def get_voice_service_dep(
    tts_provider: TTSProvider = Depends(get_tts_provider_dep),
    repository: VoiceRepository = Depends(get_voice_repository),
) -> VoiceService:
    return VoiceService(tts_provider=tts_provider, repository=repository)

"""
Voice enrollment business logic: validation, consent enforcement, provider
delegation and (in-memory, swappable) persistence of voice profiles.
"""
import uuid
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.exceptions import ConsentRequiredError, NotFoundError, ValidationError
from app.schemas.voice import ConsentDeclaration, VoiceProfile
from app.services.tts_service import TTSProvider

settings = get_settings()


class VoiceRepository:
    """In-memory store. Swap for a real Postgres/Supabase table in production —
    the interface (get/save/delete/list_for_user) is what routes depend on."""

    def __init__(self):
        self._voices: dict[str, dict] = {}

    def save(self, owner_id: str, profile: VoiceProfile) -> None:
        self._voices[profile.voice_id] = {"owner_id": owner_id, **profile.model_dump()}

    def get(self, voice_id: str) -> dict | None:
        return self._voices.get(voice_id)

    def list_for_user(self, owner_id: str) -> list[VoiceProfile]:
        return [
            VoiceProfile(**{k: v for k, v in row.items() if k != "owner_id"})
            for row in self._voices.values()
            if row["owner_id"] == owner_id
        ]

    def delete(self, voice_id: str) -> None:
        self._voices.pop(voice_id, None)


class VoiceService:
    def __init__(self, tts_provider: TTSProvider, repository: VoiceRepository):
        self.tts_provider = tts_provider
        self.repository = repository

    @staticmethod
    def validate_sample(content_type: str, size_bytes: int) -> None:
        if content_type not in settings.ALLOWED_VOICE_MIME_TYPES:
            raise ValidationError(
                f"Unsupported audio type '{content_type}'. Allowed: {settings.ALLOWED_VOICE_MIME_TYPES}"
            )
        max_bytes = settings.MAX_VOICE_SAMPLE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            raise ValidationError(f"Voice sample exceeds max size of {settings.MAX_VOICE_SAMPLE_MB}MB.")
        if size_bytes == 0:
            raise ValidationError("Voice sample file is empty.")

    @staticmethod
    def enforce_consent(consent: ConsentDeclaration) -> None:
        if not consent.consent_statement_acknowledged:
            raise ConsentRequiredError(
                "You must acknowledge the consent statement before a voice can be cloned."
            )
        if not consent.is_own_voice and not consent.third_party_permission_reference:
            raise ConsentRequiredError(
                "A third_party_permission_reference is required when cloning a voice that is not your own."
            )

    def enroll(
        self, owner_id: str, label: str, sample_bytes: bytes, filename: str, content_type: str,
        consent: ConsentDeclaration,
    ) -> VoiceProfile:
        self.validate_sample(content_type, len(sample_bytes))
        self.enforce_consent(consent)

        provider_voice_id = self.tts_provider.clone_voice(label=label, sample_bytes=sample_bytes, filename=filename)

        profile = VoiceProfile(
            voice_id=str(uuid.uuid4()),
            provider_voice_id=provider_voice_id,
            label=label,
            created_at=datetime.now(timezone.utc),
            sample_count=1,
        )
        self.repository.save(owner_id, profile)
        return profile

    def get_owned_voice(self, owner_id: str, voice_id: str) -> dict:
        row = self.repository.get(voice_id)
        if row is None or row["owner_id"] != owner_id:
            raise NotFoundError("Voice profile not found.")
        return row

    def delete(self, owner_id: str, voice_id: str) -> None:
        row = self.get_owned_voice(owner_id, voice_id)
        self.tts_provider.delete_voice(row["provider_voice_id"])
        self.repository.delete(voice_id)


_voice_repository_singleton = VoiceRepository()


def get_voice_repository() -> VoiceRepository:
    return _voice_repository_singleton

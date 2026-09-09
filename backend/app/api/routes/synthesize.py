import uuid

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_user,
    get_storage_dep,
    get_translation_service_dep,
    get_voice_service_dep,
)
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.models.user import UserRecord
from app.schemas.synth import SynthesizeRequest, SynthesizeResponse
from app.services.audio_postprocess import apply_pitch_shift, get_duration_seconds
from app.services.storage_service import StorageBackend
from app.services.translation_service import TranslationService
from app.services.tts_service import resolve_voice_settings
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/synthesize", tags=["synthesize"])
settings = get_settings()


@router.post("", response_model=SynthesizeResponse)
def synthesize_speech(
    payload: SynthesizeRequest,
    current_user: UserRecord = Depends(get_current_user),
    voice_service: VoiceService = Depends(get_voice_service_dep),
    translation_service: TranslationService = Depends(get_translation_service_dep),
    storage: StorageBackend = Depends(get_storage_dep),
):
    """
    End-to-end pipeline: (optional translate) -> resolve emotion/tone into
    provider voice settings -> synthesize with the user's cloned voice ->
    apply pitch shift -> persist audio -> return a playable URL.
    """
    # 1. Ownership check — a user may only synthesize with their own enrolled voices.
    voice_row = voice_service.get_owned_voice(current_user.id, payload.voice_id)

    # 2. Optional translation.
    final_text = payload.script
    language_used = payload.target_language
    if payload.translate_first:
        final_text, _detected = translation_service.translate(
            text=payload.script, target_language=payload.target_language
        )
    elif payload.target_language not in settings.SUPPORTED_LANGUAGES:
        raise ValidationError(f"Unsupported target language: {payload.target_language}")

    # 3. Resolve emotion/tone (or explicit override) into concrete voice settings.
    voice_settings = resolve_voice_settings(payload.emotion, payload.tone, payload.voice_settings)

    # 4. Synthesize via the cloned voice.
    result = voice_service.tts_provider.synthesize(
        provider_voice_id=voice_row["provider_voice_id"], text=final_text, voice_settings=voice_settings
    )

    # 5. Post-process pitch (provider APIs don't expose this directly).
    audio_bytes = apply_pitch_shift(result.audio_bytes, voice_settings.pitch_semitones)
    duration = get_duration_seconds(audio_bytes)

    # 6. Persist and return a URL the client can play/download.
    audio_url = storage.upload(settings.SUPABASE_AUDIO_BUCKET, audio_bytes, extension="wav")

    return SynthesizeResponse(
        job_id=str(uuid.uuid4()),
        audio_url=audio_url,
        duration_seconds=duration,
        final_text_used=final_text,
        language=language_used,
        emotion=payload.emotion,
        tone=payload.tone,
    )

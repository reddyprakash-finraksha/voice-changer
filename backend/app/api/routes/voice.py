import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_current_user, get_voice_service_dep
from app.core.exceptions import ValidationError
from app.models.user import UserRecord
from app.schemas.voice import ConsentDeclaration, VoiceEnrollResponse, VoiceProfile
from app.services.voice_service import VoiceRepository, VoiceService, get_voice_repository

router = APIRouter(prefix="/voices", tags=["voice"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/enroll", response_model=VoiceEnrollResponse, status_code=201)
async def enroll_voice(
    label: str = Form(..., min_length=1, max_length=100),
    consent: str = Form(..., description="JSON-encoded ConsentDeclaration"),
    sample: UploadFile = File(...),
    current_user: UserRecord = Depends(get_current_user),
    voice_service: VoiceService = Depends(get_voice_service_dep),
):
    """
    Registers (clones) a voice from an uploaded audio sample.
    Requires an explicit, auditable consent declaration — see ConsentDeclaration.
    """
    try:
        consent_obj = ConsentDeclaration(**json.loads(consent))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValidationError("`consent` must be a valid JSON ConsentDeclaration object.") from exc

    sample_bytes = await sample.read()
    profile = voice_service.enroll(
        owner_id=current_user.id,
        label=label,
        sample_bytes=sample_bytes,
        filename=sample.filename or "sample.wav",
        content_type=sample.content_type or "application/octet-stream",
        consent=consent_obj,
    )
    return VoiceEnrollResponse(
        voice_id=profile.voice_id,
        provider_voice_id=profile.provider_voice_id,
        status="ready",
        created_at=profile.created_at,
    )


@router.get("", response_model=list[VoiceProfile])
def list_my_voices(
    current_user: UserRecord = Depends(get_current_user),
    repository: VoiceRepository = Depends(get_voice_repository),
):
    return repository.list_for_user(current_user.id)


@router.delete("/{voice_id}", status_code=204)
def delete_voice(
    voice_id: str,
    current_user: UserRecord = Depends(get_current_user),
    voice_service: VoiceService = Depends(get_voice_service_dep),
):
    voice_service.delete(current_user.id, voice_id)
    return None

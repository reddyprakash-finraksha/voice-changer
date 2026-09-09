from fastapi import APIRouter, Depends

from app.api.deps import get_translation_service_dep
from app.models.user import UserRecord
from app.api.deps import get_current_user
from app.schemas.synth import TranslateRequest, TranslateResponse
from app.services.translation_service import TranslationService

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post("", response_model=TranslateResponse)
def translate_text(
    payload: TranslateRequest,
    current_user: UserRecord = Depends(get_current_user),
    service: TranslationService = Depends(get_translation_service_dep),
):
    translated, detected = service.translate(
        text=payload.text, target_language=payload.target_language, source_language=payload.source_language
    )
    return TranslateResponse(
        source_language_detected=detected, target_language=payload.target_language, translated_text=translated
    )

from datetime import datetime

from pydantic import BaseModel, Field


class ConsentDeclaration(BaseModel):
    """
    Explicit, auditable consent captured at voice-enrollment time.
    Required by law in most jurisdictions before cloning anyone's voice,
    including the user's own, for commercial use.
    """
    full_legal_name: str = Field(min_length=1, max_length=200)
    consent_statement_acknowledged: bool = Field(
        description="Must be true: user confirms the uploaded sample is their own voice, "
                     "or that of a person who has separately granted written permission."
    )
    is_own_voice: bool
    third_party_permission_reference: str | None = Field(
        default=None,
        description="Required if is_own_voice is False: a reference/ID to the signed permission on file.",
    )


class VoiceEnrollResponse(BaseModel):
    voice_id: str
    provider_voice_id: str
    status: str
    created_at: datetime


class VoiceProfile(BaseModel):
    voice_id: str
    provider_voice_id: str
    label: str
    created_at: datetime
    sample_count: int

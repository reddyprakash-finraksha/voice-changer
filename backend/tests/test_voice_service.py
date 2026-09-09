import pytest

from app.core.exceptions import ConsentRequiredError, ValidationError
from app.schemas.voice import ConsentDeclaration
from app.services.tts_service import SynthesisResult, TTSProvider
from app.services.voice_service import VoiceRepository, VoiceService


class FakeTTSProvider(TTSProvider):
    def clone_voice(self, label, sample_bytes, filename):
        return "provider-voice-123"

    def synthesize(self, provider_voice_id, text, voice_settings):
        return SynthesisResult(audio_bytes=b"fake-audio")

    def delete_voice(self, provider_voice_id):
        pass


@pytest.fixture
def voice_service():
    return VoiceService(tts_provider=FakeTTSProvider(), repository=VoiceRepository())


def _consent(**overrides):
    base = dict(full_legal_name="Reddyprakash", consent_statement_acknowledged=True, is_own_voice=True)
    base.update(overrides)
    return ConsentDeclaration(**base)


def test_enroll_succeeds_with_valid_consent(voice_service):
    profile = voice_service.enroll(
        owner_id="user-1", label="My Voice", sample_bytes=b"x" * 1000,
        filename="sample.wav", content_type="audio/wav", consent=_consent(),
    )
    assert profile.provider_voice_id == "provider-voice-123"


def test_enroll_rejects_without_consent_ack(voice_service):
    with pytest.raises(ConsentRequiredError):
        voice_service.enroll(
            owner_id="user-1", label="My Voice", sample_bytes=b"x" * 1000,
            filename="sample.wav", content_type="audio/wav",
            consent=_consent(consent_statement_acknowledged=False),
        )


def test_enroll_rejects_third_party_voice_without_reference(voice_service):
    with pytest.raises(ConsentRequiredError):
        voice_service.enroll(
            owner_id="user-1", label="Friend's Voice", sample_bytes=b"x" * 1000,
            filename="sample.wav", content_type="audio/wav",
            consent=_consent(is_own_voice=False, third_party_permission_reference=None),
        )


def test_enroll_rejects_oversized_file(voice_service):
    huge = b"x" * (16 * 1024 * 1024)
    with pytest.raises(ValidationError):
        voice_service.enroll(
            owner_id="user-1", label="Big", sample_bytes=huge,
            filename="sample.wav", content_type="audio/wav", consent=_consent(),
        )


def test_enroll_rejects_bad_mime_type(voice_service):
    with pytest.raises(ValidationError):
        voice_service.enroll(
            owner_id="user-1", label="Bad Type", sample_bytes=b"x" * 1000,
            filename="sample.txt", content_type="text/plain", consent=_consent(),
        )


def test_ownership_enforced_on_lookup(voice_service):
    profile = voice_service.enroll(
        owner_id="user-1", label="Mine", sample_bytes=b"x" * 1000,
        filename="sample.wav", content_type="audio/wav", consent=_consent(),
    )
    with pytest.raises(Exception):
        voice_service.get_owned_voice("someone-else", profile.voice_id)

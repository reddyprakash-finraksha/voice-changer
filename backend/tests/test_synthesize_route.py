"""
Integration-style test for the /synthesize endpoint using dependency
overrides so no real ElevenLabs/Supabase calls are made.
"""
import json

from app.api.deps import get_storage_dep, get_voice_service_dep
from app.main import app
from app.services.tts_service import SynthesisResult, TTSProvider
from app.services.voice_service import VoiceRepository, VoiceService


class FakeTTSProvider(TTSProvider):
    def clone_voice(self, label, sample_bytes, filename):
        return "provider-voice-abc"

    def synthesize(self, provider_voice_id, text, voice_settings):
        # Minimal valid WAV header + silence, so downstream duration/pitch code works.
        import io
        import numpy as np
        import soundfile as sf
        buf = io.BytesIO()
        sf.write(buf, np.zeros(16000, dtype="float32"), 16000, format="WAV")
        return SynthesisResult(audio_bytes=buf.getvalue())

    def delete_voice(self, provider_voice_id):
        pass


class FakeStorage:
    def upload(self, bucket, data, extension):
        return "https://fake-storage/audio.wav"


def _consent_json():
    return json.dumps(
        {"full_legal_name": "Test User", "consent_statement_acknowledged": True, "is_own_voice": True}
    )


def test_full_pipeline_enroll_then_synthesize(client, auth_headers):
    fake_repo = VoiceRepository()
    fake_service = VoiceService(tts_provider=FakeTTSProvider(), repository=fake_repo)

    app.dependency_overrides[get_voice_service_dep] = lambda: fake_service
    app.dependency_overrides[get_storage_dep] = lambda: FakeStorage()
    try:
        enroll_resp = client.post(
            "/api/v1/voices/enroll",
            headers=auth_headers,
            data={"label": "My Voice", "consent": _consent_json()},
            files={"sample": ("sample.wav", b"x" * 2000, "audio/wav")},
        )
        assert enroll_resp.status_code == 201
        voice_id = enroll_resp.json()["voice_id"]

        synth_resp = client.post(
            "/api/v1/synthesize",
            headers=auth_headers,
            json={
                "voice_id": voice_id,
                "script": "Welcome to FinRaksha AI.",
                "target_language": "en",
                "translate_first": False,
                "emotion": "excited",
                "tone": "advertisement",
            },
        )
        assert synth_resp.status_code == 200
        body = synth_resp.json()
        assert body["audio_url"] == "https://fake-storage/audio.wav"
        assert body["emotion"] == "excited"
    finally:
        app.dependency_overrides.clear()


def test_synthesize_rejects_voice_not_owned(client, auth_headers):
    resp = client.post(
        "/api/v1/synthesize",
        headers=auth_headers,
        json={"voice_id": "nonexistent-voice", "script": "Hello", "target_language": "en"},
    )
    assert resp.status_code == 404

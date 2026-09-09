"""
Voice cloning + emotional text-to-speech via ElevenLabs.

Why ElevenLabs: it is currently the most production-ready provider offering
(a) consented voice cloning from a short sample and (b) fine-grained
stability/similarity/style controls that map cleanly onto "emotion" and
"tone". Pitch is not exposed by the provider API, so it is layered on top
in `audio_postprocess.py`. The provider is isolated behind `TTSProvider`
so it can be swapped (e.g. for Azure Neural TTS or Coqui XTTS self-hosted)
without touching routes or business logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.schemas.synth import EmotionPreset, ToneStyle, VoiceSettings

settings = get_settings()


# ---------------------------------------------------------------------------
# Emotion/tone -> provider voice-setting mapping
# ---------------------------------------------------------------------------
# stability: lower => more expressive & variable delivery
# similarity_boost: higher => stays closer to the cloned voice timbre
# style: higher => stronger exaggeration of the target style
_EMOTION_DEFAULTS: dict[EmotionPreset, VoiceSettings] = {
    EmotionPreset.NEUTRAL:    VoiceSettings(stability=0.6, similarity_boost=0.8, style_exaggeration=0.15, speed=1.0),
    EmotionPreset.HAPPY:      VoiceSettings(stability=0.35, similarity_boost=0.75, style_exaggeration=0.55, speed=1.05),
    EmotionPreset.SAD:        VoiceSettings(stability=0.65, similarity_boost=0.8, style_exaggeration=0.35, speed=0.9),
    EmotionPreset.ANGRY:      VoiceSettings(stability=0.3, similarity_boost=0.7, style_exaggeration=0.7, speed=1.05),
    EmotionPreset.EXCITED:    VoiceSettings(stability=0.25, similarity_boost=0.7, style_exaggeration=0.65, speed=1.1),
    EmotionPreset.CALM:       VoiceSettings(stability=0.75, similarity_boost=0.85, style_exaggeration=0.1, speed=0.95),
    EmotionPreset.SERIOUS:    VoiceSettings(stability=0.7, similarity_boost=0.85, style_exaggeration=0.2, speed=0.95),
    EmotionPreset.EMPATHETIC: VoiceSettings(stability=0.55, similarity_boost=0.85, style_exaggeration=0.3, speed=0.95),
}

# Tone nudges the emotion defaults slightly (e.g. "news" tightens stability further).
_TONE_STABILITY_DELTA: dict[ToneStyle, float] = {
    ToneStyle.CONVERSATIONAL: 0.0,
    ToneStyle.FORMAL: 0.1,
    ToneStyle.NARRATIVE: -0.05,
    ToneStyle.ADVERTISEMENT: -0.1,
    ToneStyle.NEWS: 0.15,
}


def resolve_voice_settings(
    emotion: EmotionPreset, tone: ToneStyle, override: VoiceSettings | None
) -> VoiceSettings:
    if override is not None:
        return override
    base = _EMOTION_DEFAULTS[emotion]
    delta = _TONE_STABILITY_DELTA.get(tone, 0.0)
    stability = min(1.0, max(0.0, base.stability + delta))
    return VoiceSettings(
        stability=stability,
        similarity_boost=base.similarity_boost,
        style_exaggeration=base.style_exaggeration,
        speed=base.speed,
        pitch_semitones=0.0,
    )


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    content_type: str = "audio/wav"


class TTSProvider(ABC):
    @abstractmethod
    def clone_voice(self, label: str, sample_bytes: bytes, filename: str) -> str:
        """Registers a voice sample with the provider; returns the provider's voice id."""
        raise NotImplementedError

    @abstractmethod
    def synthesize(self, provider_voice_id: str, text: str, voice_settings: VoiceSettings) -> SynthesisResult:
        raise NotImplementedError

    @abstractmethod
    def delete_voice(self, provider_voice_id: str) -> None:
        raise NotImplementedError


class ElevenLabsProvider(TTSProvider):
    def __init__(self, cfg: Settings | None = None):
        self.cfg = cfg or settings
        if not self.cfg.ELEVENLABS_API_KEY:
            # We deliberately don't raise here: allows the app (and its tests)
            # to boot without a key. The error surfaces on first real call.
            pass

    def _headers(self) -> dict:
        return {"xi-api-key": self.cfg.ELEVENLABS_API_KEY}

    def _require_key(self) -> None:
        if not self.cfg.ELEVENLABS_API_KEY:
            raise UpstreamServiceError(
                "ELEVENLABS_API_KEY is not configured. Set it in your environment to enable voice cloning/TTS."
            )

    def clone_voice(self, label: str, sample_bytes: bytes, filename: str) -> str:
        self._require_key()
        url = f"{self.cfg.ELEVENLABS_BASE_URL}/voices/add"
        try:
            response = httpx.post(
                url,
                headers=self._headers(),
                data={"name": label},
                files={"files": (filename, sample_bytes)},
                timeout=self.cfg.ELEVENLABS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            voice_id = payload.get("voice_id")
            if not voice_id:
                raise UpstreamServiceError("Voice cloning provider did not return a voice_id.")
            return voice_id
        except httpx.HTTPStatusError as exc:
            raise UpstreamServiceError(
                f"Voice cloning failed ({exc.response.status_code}): {exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"Voice cloning request failed: {exc}") from exc

    def synthesize(self, provider_voice_id: str, text: str, voice_settings: VoiceSettings) -> SynthesisResult:
        self._require_key()
        if not text.strip():
            raise ValidationError("Text to synthesize must not be empty.")

        url = f"{self.cfg.ELEVENLABS_BASE_URL}/text-to-speech/{provider_voice_id}"
        body = {
            "text": text,
            "model_id": self.cfg.ELEVENLABS_MODEL_ID,
            "voice_settings": {
                "stability": voice_settings.stability,
                "similarity_boost": voice_settings.similarity_boost,
                "style": voice_settings.style_exaggeration,
                "use_speaker_boost": True,
                "speed": voice_settings.speed,
            },
        }
        try:
            response = httpx.post(
                url,
                headers={**self._headers(), "Accept": "audio/mpeg", "Content-Type": "application/json"},
                json=body,
                timeout=self.cfg.ELEVENLABS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return SynthesisResult(audio_bytes=response.content, content_type="audio/mpeg")
        except httpx.HTTPStatusError as exc:
            raise UpstreamServiceError(
                f"Speech synthesis failed ({exc.response.status_code}): {exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"Speech synthesis request failed: {exc}") from exc

    def delete_voice(self, provider_voice_id: str) -> None:
        self._require_key()
        url = f"{self.cfg.ELEVENLABS_BASE_URL}/voices/{provider_voice_id}"
        try:
            response = httpx.delete(url, headers=self._headers(), timeout=self.cfg.ELEVENLABS_TIMEOUT_SECONDS)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"Failed to delete voice: {exc}") from exc


def get_tts_provider() -> TTSProvider:
    return ElevenLabsProvider()

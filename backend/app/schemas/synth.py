from enum import Enum

from pydantic import BaseModel, Field, model_validator


class EmotionPreset(str, Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    EXCITED = "excited"
    CALM = "calm"
    SERIOUS = "serious"
    EMPATHETIC = "empathetic"


class ToneStyle(str, Enum):
    CONVERSATIONAL = "conversational"
    FORMAL = "formal"
    NARRATIVE = "narrative"
    ADVERTISEMENT = "advertisement"
    NEWS = "news"


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    source_language: str = Field(default="auto", description="ISO 639-1 code or 'auto'")
    target_language: str = Field(min_length=2, max_length=5)


class TranslateResponse(BaseModel):
    source_language_detected: str
    target_language: str
    translated_text: str


class VoiceSettings(BaseModel):
    """Fine-grained controls layered on top of an emotion preset."""
    stability: float = Field(default=0.5, ge=0.0, le=1.0, description="Lower = more expressive/variable")
    similarity_boost: float = Field(default=0.75, ge=0.0, le=1.0, description="Higher = closer to source voice")
    style_exaggeration: float = Field(default=0.3, ge=0.0, le=1.0, description="Higher = stronger stylistic delivery")
    speed: float = Field(default=1.0, ge=0.7, le=1.2, description="Playback speed multiplier")
    pitch_semitones: float = Field(default=0.0, ge=-6.0, le=6.0, description="Pitch shift in semitones, applied in post-processing")


class SynthesizeRequest(BaseModel):
    voice_id: str
    script: str = Field(min_length=1, max_length=5000)
    target_language: str = Field(default="en")
    translate_first: bool = Field(default=False, description="If true, `script` is translated to target_language before synthesis")
    emotion: EmotionPreset = Field(default=EmotionPreset.NEUTRAL)
    tone: ToneStyle = Field(default=ToneStyle.CONVERSATIONAL)
    voice_settings: VoiceSettings | None = Field(default=None, description="Overrides emotion preset defaults if provided")

    @model_validator(mode="after")
    def _check_language_consistency(self):
        if self.translate_first and not self.target_language:
            raise ValueError("target_language is required when translate_first is True")
        return self


class SynthesizeResponse(BaseModel):
    job_id: str
    audio_url: str
    duration_seconds: float
    final_text_used: str
    language: str
    emotion: EmotionPreset
    tone: ToneStyle

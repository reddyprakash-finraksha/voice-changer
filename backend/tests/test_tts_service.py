import pytest

from app.schemas.synth import EmotionPreset, ToneStyle, VoiceSettings
from app.services.tts_service import resolve_voice_settings


def test_resolve_voice_settings_uses_emotion_defaults():
    settings = resolve_voice_settings(EmotionPreset.HAPPY, ToneStyle.CONVERSATIONAL, override=None)
    assert settings.stability == pytest.approx(0.35)
    assert settings.speed == pytest.approx(1.05)


def test_resolve_voice_settings_applies_tone_delta():
    neutral_conversational = resolve_voice_settings(EmotionPreset.NEUTRAL, ToneStyle.CONVERSATIONAL, None)
    neutral_news = resolve_voice_settings(EmotionPreset.NEUTRAL, ToneStyle.NEWS, None)
    assert neutral_news.stability > neutral_conversational.stability


def test_resolve_voice_settings_clamps_to_valid_range():
    settings = resolve_voice_settings(EmotionPreset.CALM, ToneStyle.NEWS, None)
    assert 0.0 <= settings.stability <= 1.0


def test_explicit_override_bypasses_presets():
    custom = VoiceSettings(stability=0.9, similarity_boost=0.5, style_exaggeration=0.1, speed=1.0)
    resolved = resolve_voice_settings(EmotionPreset.ANGRY, ToneStyle.FORMAL, override=custom)
    assert resolved is custom

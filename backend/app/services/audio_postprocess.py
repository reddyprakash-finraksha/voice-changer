"""
Post-processing applied to raw TTS output:
  - Pitch shifting (semitones) — most TTS providers don't expose this directly,
    so we do it ourselves with librosa's phase-vocoder pitch shift, which
    preserves speed/formant timing while changing pitch.
  - Simple duration measurement for the API response.

Kept as a separate, independently-testable unit so it can be swapped out
(e.g. for a GPU-accelerated pipeline) without touching the TTS or API layers.
"""
import io

import numpy as np
import soundfile as sf

from app.core.exceptions import ValidationError


def apply_pitch_shift(audio_bytes: bytes, semitones: float, sample_rate_hint: int | None = None) -> bytes:
    """
    Shift the pitch of an audio clip by `semitones` (-6..+6) without
    changing its duration. Returns re-encoded WAV bytes.
    """
    if semitones == 0:
        return audio_bytes

    try:
        import librosa
    except ImportError as exc:  # pragma: no cover
        raise ValidationError("Pitch-shift dependency (librosa) not installed.") from exc

    try:
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)  # downmix to mono for consistent processing
        shifted = librosa.effects.pitch_shift(y=data, sr=sr, n_steps=semitones)
        out_buffer = io.BytesIO()
        sf.write(out_buffer, shifted, sr, format="WAV")
        return out_buffer.getvalue()
    except Exception as exc:
        raise ValidationError(f"Failed to apply pitch shift: {exc}") from exc


def get_duration_seconds(audio_bytes: bytes) -> float:
    try:
        info = sf.info(io.BytesIO(audio_bytes))
        return round(info.frames / float(info.samplerate), 2)
    except Exception:
        return 0.0

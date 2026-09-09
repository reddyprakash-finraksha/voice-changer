"""
Pluggable translation layer. Default provider is a free Google-Translate-backed
provider (deep-translator) so the app works out of the box with zero paid keys.
Swap TRANSLATION_PROVIDER=deepl or openai in .env for higher-quality output.
"""
from abc import ABC, abstractmethod

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError

settings = get_settings()


class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, text: str, target_language: str, source_language: str = "auto") -> tuple[str, str]:
        """Returns (translated_text, detected_source_language)."""
        raise NotImplementedError


class GoogleFreeTranslationProvider(TranslationProvider):
    """Uses deep-translator's free Google Translate backend. No API key required."""

    def translate(self, text: str, target_language: str, source_language: str = "auto") -> tuple[str, str]:
        try:
            from deep_translator import GoogleTranslator
        except ImportError as exc:  # pragma: no cover
            raise UpstreamServiceError("Translation dependency not installed.") from exc

        try:
            translator = GoogleTranslator(source=source_language, target=target_language)
            translated = translator.translate(text)
            detected = source_language if source_language != "auto" else "auto-detected"
            if not translated:
                raise UpstreamServiceError("Translation provider returned an empty result.")
            return translated, detected
        except Exception as exc:  # deep_translator raises generic exceptions
            raise UpstreamServiceError(f"Translation failed: {exc}") from exc


class DeepLTranslationProvider(TranslationProvider):
    def translate(self, text: str, target_language: str, source_language: str = "auto") -> tuple[str, str]:
        import httpx

        if not settings.DEEPL_API_KEY:
            raise UpstreamServiceError("DeepL API key not configured.")

        try:
            resp = httpx.post(
                "https://api-free.deepl.com/v2/translate",
                data={
                    "auth_key": settings.DEEPL_API_KEY,
                    "text": text,
                    "target_lang": target_language.upper(),
                    **({"source_lang": source_language.upper()} if source_language != "auto" else {}),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            translation = data["translations"][0]
            return translation["text"], translation.get("detected_source_language", "auto-detected")
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"DeepL request failed: {exc}") from exc
        except (KeyError, IndexError) as exc:
            raise UpstreamServiceError("Unexpected DeepL response shape.") from exc


def get_translation_provider(cfg: Settings | None = None) -> TranslationProvider:
    cfg = cfg or settings
    if cfg.TRANSLATION_PROVIDER == "deepl":
        return DeepLTranslationProvider()
    return GoogleFreeTranslationProvider()


class TranslationService:
    def __init__(self, provider: TranslationProvider | None = None):
        self.provider = provider or get_translation_provider()

    def translate(self, text: str, target_language: str, source_language: str = "auto") -> tuple[str, str]:
        text = (text or "").strip()
        if not text:
            raise ValidationError("Text to translate must not be empty.")
        if len(text) > settings.MAX_SCRIPT_CHARS:
            raise ValidationError(f"Text exceeds max length of {settings.MAX_SCRIPT_CHARS} characters.")
        if target_language not in settings.SUPPORTED_LANGUAGES:
            raise ValidationError(f"Unsupported target language: {target_language}")
        return self.provider.translate(text, target_language, source_language)

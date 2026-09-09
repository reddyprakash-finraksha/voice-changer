from unittest.mock import patch

import pytest

from app.core.exceptions import ValidationError
from app.services.translation_service import TranslationService, TranslationProvider


class FakeProvider(TranslationProvider):
    def translate(self, text, target_language, source_language="auto"):
        return f"[{target_language}] {text}", "en"


def test_translate_success():
    service = TranslationService(provider=FakeProvider())
    translated, detected = service.translate("Hello world", "hi")
    assert translated == "[hi] Hello world"
    assert detected == "en"


def test_translate_rejects_empty_text():
    service = TranslationService(provider=FakeProvider())
    with pytest.raises(ValidationError):
        service.translate("   ", "hi")


def test_translate_rejects_unsupported_language():
    service = TranslationService(provider=FakeProvider())
    with pytest.raises(ValidationError):
        service.translate("Hello", "xx")


def test_translate_rejects_overlength_text():
    service = TranslationService(provider=FakeProvider())
    with pytest.raises(ValidationError):
        service.translate("a" * 6000, "hi")

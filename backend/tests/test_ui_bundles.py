import json
import re
from pathlib import Path


UI_DIRECTORY = Path(__file__).resolve().parents[1] / "static" / "ui"
LOCALES = ("en", "vi", "zh", "ja", "ko")


def test_ui_bundles_have_matching_keys_and_placeholders() -> None:
    bundles = {
        locale: json.loads((UI_DIRECTORY / f"{locale}.json").read_text(encoding="utf-8"))
        for locale in LOCALES
    }
    english = bundles["en"]

    for locale, bundle in bundles.items():
        assert bundle.keys() == english.keys(), f"{locale} bundle keys differ from en"
        for key, english_value in english.items():
            english_placeholders = set(re.findall(r"\{(\w+)\}", english_value))
            localized_placeholders = set(re.findall(r"\{(\w+)\}", bundle[key]))
            assert localized_placeholders == english_placeholders, (
                f"{locale}.{key} placeholders differ from en"
            )

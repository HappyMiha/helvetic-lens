"""Product-locale rules kept separate from official document languages."""

from __future__ import annotations

import re

SUPPORTED_LOCALES = ("de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH")
SUPPORTED_LOCALE_SET = frozenset(SUPPORTED_LOCALES)
LANGUAGE_TO_LOCALE = {value.split("-", 1)[0]: value for value in SUPPORTED_LOCALES}


def normalize_locale(value: str | None, default: str = "en-CH") -> str:
    """Return a supported locale without treating document language as a preference."""

    candidate = (value or "").strip().replace("_", "-")
    if candidate in SUPPORTED_LOCALE_SET:
        return candidate
    language = candidate.split("-", 1)[0].casefold()
    fallback = default if default in SUPPORTED_LOCALE_SET or default == "" else "en-CH"
    return LANGUAGE_TO_LOCALE.get(language, fallback)


def locale_from_accept_language(value: str | None, default: str = "en-CH") -> str:
    """Apply HTTP language preference weights and select only the explicit locale set."""

    choices: list[tuple[float, int, str]] = []
    for position, part in enumerate((value or "").split(",")):
        bits = [item.strip() for item in part.split(";")]
        language = bits[0]
        quality = 1.0
        for parameter in bits[1:]:
            match = re.fullmatch(r"q=(0(?:\.\d+)?|1(?:\.0+)?)", parameter, re.I)
            if match:
                quality = float(match.group(1))
        normalized = normalize_locale(language, "")
        if normalized:
            choices.append((quality, -position, normalized))
    return max(choices, default=(0.0, 0, default))[2]

"""Internationalisation package for R6 Navigator.

Public API
----------
current_lang() -> str
    Returns the active language code: 'fr' or 'en'.

set_lang(lang: str) -> None
    Changes the active language. Called by the UI language combobox.
    Does NOT trigger a UI redraw — that is the caller's responsibility.

t(key: str, **kwargs) -> str
    Returns the translated string for the given key in the active language.
    Falls back to the key itself if not found.
    Supports str.format() placeholders: t("app.title_with_capacity", capacity_id="I1a", label="Test")
"""

from __future__ import annotations

import json
from pathlib import Path

_I18N_DIR = Path(__file__).parent
_CACHE: dict[str, dict[str, str]] = {}
_CURRENT_LANG: str = "fr"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def current_lang() -> str:
    """Returns the active language code ('fr' or 'en')."""
    return _CURRENT_LANG


def set_lang(lang: str) -> None:
    """Sets the active language. Raises ValueError for unsupported codes."""
    global _CURRENT_LANG
    if lang not in ("fr", "en"):
        raise ValueError(f"Unsupported language: {lang!r}. Must be 'fr' or 'en'.")
    _CURRENT_LANG = lang


def t(key: str, **kwargs) -> str:
    """Returns the translated string for key in the active language.

    Unknown keys return the key itself (never raises).
    Placeholders use str.format() syntax: {capacity_id}, {label}, etc.
    """
    strings = _load(_CURRENT_LANG)
    template = strings.get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template


# ---------------------------------------------------------------------------
# Internal loader (lazy, cached)
# ---------------------------------------------------------------------------

def _load(lang: str) -> dict[str, str]:
    if lang not in _CACHE:
        path = _I18N_DIR / f"{lang}.json"
        with open(path, encoding="utf-8") as f:
            data: dict[str, str] = json.load(f)
        # Strip meta-keys (prefixed with '_')
        _CACHE[lang] = {k: v for k, v in data.items() if not k.startswith("_")}
    return _CACHE[lang]

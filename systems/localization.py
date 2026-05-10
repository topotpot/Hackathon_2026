
import json
import os

ROOT     = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOC_DIR  = os.path.join(ROOT, "localization")
SAVE_FILE = os.path.join(ROOT, "save", "settings.json")

LANGUAGES   = ["en", "ua"]
LANG_LABELS = {"en": "ENGLISH", "ua": "УКРАЇНСЬКА"}


class _Loc:

    def __init__(self) -> None:
        self._lang: str = "en"
        self._cache: dict[str, dict] = {}
        self._load("en")
        self._restore()

    def _load(self, lang: str) -> None:
        if lang in self._cache:
            return
        path = os.path.join(LOC_DIR, f"{lang}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                self._cache[lang] = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            self._cache[lang] = {}

    def _restore(self) -> None:
        try:
            with open(SAVE_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            lang = data.get("lang", "en")
            if lang in LANGUAGES:
                self._lang = lang
                self._load(lang)
        except Exception:
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
        existing: dict = {}
        try:
            with open(SAVE_FILE, encoding="utf-8") as fh:
                existing = json.load(fh)
        except Exception:
            pass
        existing["lang"] = self._lang
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as fh:
                json.dump(existing, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @property
    def lang(self) -> str:
        return self._lang

    def set_language(self, lang: str) -> None:
        if lang in LANGUAGES and lang != self._lang:
            self._lang = lang
            self._load(lang)
            self._save()

    def next_language(self) -> None:
        idx = LANGUAGES.index(self._lang) if self._lang in LANGUAGES else 0
        self.set_language(LANGUAGES[(idx + 1) % len(LANGUAGES)])

    def get(self, key: str):
        """Return raw value (any type) at dot-path key, with English fallback."""
        val = self._resolve(key, self._lang)
        if val is None and self._lang != "en":
            val = self._resolve(key, "en")
        return val

    def t(self, key: str, **kwargs) -> str:
        val = self.get(key)
        if val is None:
            return key
        if isinstance(val, str):
            return val.format(**kwargs) if kwargs else val
        return str(val)

    def _resolve(self, key: str, lang: str):
        data = self._cache.get(lang, {})
        node = data
        for part in key.split("."):
            if isinstance(node, dict):
                node = node.get(part)
            else:
                return None
        return node


_loc = _Loc()


def t(key: str, **kwargs) -> str:
    return _loc.t(key, **kwargs)

def get(key: str):
    return _loc.get(key)

def set_language(lang: str) -> None:
    _loc.set_language(lang)

def next_language() -> None:
    _loc.next_language()

def current_lang() -> str:
    return _loc.lang

def lang_label(lang: str | None = None) -> str:
    if lang is None:
        lang = _loc.lang
    return LANG_LABELS.get(lang, lang.upper())

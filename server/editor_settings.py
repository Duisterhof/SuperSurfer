"""Editor defaults shared by every project on this connected workspace."""
from copy import deepcopy
from .surfboards import SurfboardError

DEFAULTS = {"engine": "monaco", "theme": "match", "font_size": 13, "tab_size": 4,
            "word_wrap": "auto", "minimap": False, "latex_spellcheck": True,
            "latex_auto_compile": True, "dictionary": []}


def read(store):
    return {**deepcopy(DEFAULTS), **store.get("editor_settings", {})}


def save(store, fields):
    if not isinstance(fields, dict) or set(fields) - set(DEFAULTS):
        raise SurfboardError("Unknown editor setting")
    result = read(store)
    for key, value in fields.items():
        if key in {"font_size", "tab_size"}:
            low, high = (8, 32) if key == "font_size" else (1, 8)
            if type(value) is not int or not low <= value <= high:
                raise SurfboardError(f"{key} must be {low}–{high}")
        elif key in {"minimap", "latex_spellcheck", "latex_auto_compile"}:
            if type(value) is not bool:
                raise SurfboardError(key + " must be a boolean")
        elif key == "dictionary":
            if (not isinstance(value, list) or len(value) > 2000 or
                    any(not isinstance(word, str) or not word.isalpha() or len(word) > 80 for word in value)):
                raise SurfboardError("Custom dictionary supports up to 2,000 words")
            value = sorted(set(value))
        elif key == "theme":
            if not isinstance(value, str) or not 1 <= len(value) <= 200 or any(ord(c) < 32 for c in value):
                raise SurfboardError("Choose an editor theme")
        elif key == "engine" and value not in {"monaco", "vscode"}:
            raise SurfboardError("Choose the built-in editor or VS Code workbench")
        elif key == "word_wrap" and value not in {"auto", "on", "off"}:
            raise SurfboardError("Choose automatic, on, or off word wrapping")
        result[key] = value
    store.put("editor_settings", result)
    return result

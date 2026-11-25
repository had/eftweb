"""Read and write installation-wide application settings."""

import json
import os
import tempfile
from pathlib import Path

from flask import current_app

DEFAULT_THEME = "sage-slate"
VALID_THEMES = {"sage-slate", "mist-blue", "warm-stone", "midnight-slate"}
DEFAULT_NUMBER_LOCALE = "en-GB"
VALID_NUMBER_LOCALES = {"en-GB", "en-US", "fr-FR", "de-DE", "es-ES", "it-IT"}
DEFAULT_SETTINGS = {"theme": DEFAULT_THEME, "number_locale": DEFAULT_NUMBER_LOCALE}


def settings_path():
    return Path(current_app.config["SETTINGS_FILE"])


def read_settings():
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_SETTINGS.copy()
    except json.JSONDecodeError:
        current_app.logger.warning("Invalid settings JSON in %s; using defaults", path)
        return DEFAULT_SETTINGS.copy()

    result = DEFAULT_SETTINGS.copy()
    for key, valid_values in (("theme", VALID_THEMES), ("number_locale", VALID_NUMBER_LOCALES)):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, str) and value in valid_values:
            result[key] = value
        elif value is not None:
            current_app.logger.warning("Invalid %s setting in %s; using default", key, path)
    return result


def write_settings(settings):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".settings-", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(settings, temporary_file, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

"""Read and write installation-wide application settings."""

import json
import os
import tempfile
from pathlib import Path

from flask import current_app

DEFAULT_THEME = "sage-slate"
VALID_THEMES = {"sage-slate", "mist-blue", "warm-stone"}


def settings_path():
    return Path(current_app.config["SETTINGS_FILE"])


def read_settings():
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"theme": DEFAULT_THEME}
    except json.JSONDecodeError:
        current_app.logger.warning("Invalid settings JSON in %s; using defaults", path)
        return {"theme": DEFAULT_THEME}

    theme = data.get("theme") if isinstance(data, dict) else None
    if not isinstance(theme, str) or theme not in VALID_THEMES:
        current_app.logger.warning("Invalid theme setting in %s; using defaults", path)
        return {"theme": DEFAULT_THEME}
    return {"theme": theme}


def write_settings(theme):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".settings-", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump({"theme": theme}, temporary_file, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

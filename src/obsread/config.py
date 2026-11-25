"""User configuration; reads never depend on the working directory."""

import json
import os
import sys
import tempfile
from pathlib import Path

from .errors import ObsreadError


def config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "obsread/config.json"


def load_config() -> dict:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (ValueError, UnicodeError) as exc:
        raise ObsreadError(f"Invalid configuration {path}: {exc}") from exc
    if not isinstance(data, dict) or (
        "vault" in data and (not isinstance(data["vault"], str) or not data["vault"].strip())
    ):
        raise ObsreadError(f"Invalid configuration {path}: vault must be a nonempty string")
    return data


def validate_vault(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ObsreadError(f"Vault is not an existing directory: {path}")
    return path


def resolve_vault(explicit: str | None = None) -> Path:
    value = explicit or os.environ.get("OBSREAD_VAULT") or load_config().get("vault")
    if not value:
        raise ObsreadError(
            "No vault configured. Run obsread config set vault PATH, "
            "set OBSREAD_VAULT, or pass --vault PATH."
        )
    return validate_vault(value)


def set_vault(value: str) -> Path:
    vault = validate_vault(value)
    data = load_config()
    data["vault"] = str(vault)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path

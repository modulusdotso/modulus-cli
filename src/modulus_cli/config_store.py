import json
import os
from pathlib import Path
from typing import Any, Optional


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / "modulus"


def credentials_path() -> Path:
    return _config_dir() / "credentials.json"


def save_api_key(api_key: str) -> None:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"api_key": api_key}
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_api_key() -> Optional[str]:
    path = credentials_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    key = data.get("api_key")
    return key if isinstance(key, str) and key else None

import json
from pathlib import Path
from typing import Any, Dict, List

from logger import logger

SETTINGS_PATH = Path(__file__).parent / "settings.json"


class SettingsError(RuntimeError):
    """Raised when settings.json cannot be parsed."""


def _ensure_list(value: Any, default: List[str]) -> List[str]:
    if value is None:
        return list(default)
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def load_settings(path: Path | str | None = None) -> Dict[str, Any]:
    config_path = Path(path) if path else SETTINGS_PATH
    if not config_path.exists():
        raise SettingsError(f"settings file not found: {config_path}")

    logger.info("Loading settings from %s", config_path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    required_keys = ["type", "listen", "send", "ip", "group", "private", "superadmin"]
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise SettingsError(f"Missing required keys in settings: {', '.join(missing)}")

    data["group"] = _ensure_list(data.get("group"), [])
    data["private"] = _ensure_list(data.get("private"), [])
    data["superadmin"] = _ensure_list(data.get("superadmin"), [])

    workers = data.get("workers", 4)
    data["workers"] = workers if isinstance(workers, int) and workers > 0 else 4

    if data["type"].lower() != "http":
        raise SettingsError("Current implementation only supports HTTP transport")

    return data

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional

from logger import logger

PLUGIN_PACKAGE = "plugins"
PLUGIN_PREFIX = "plugins_"


class PluginManager:
    """Loads and dispatches plugin handlers."""

    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings
        self.modules: List[ModuleType] = []
        self._load_plugins()

    def _load_plugins(self) -> None:
        package_path = Path(__file__).parent / PLUGIN_PACKAGE
        if not package_path.exists():
            logger.error("Plugin directory not found: %s", package_path)
            return

        for module in pkgutil.iter_modules([str(package_path)]):
            if not module.name.startswith(PLUGIN_PREFIX):
                continue
            full_name = f"{PLUGIN_PACKAGE}.{module.name}"
            try:
                imported = importlib.import_module(full_name)
                if hasattr(imported, "handle"):
                    self.modules.append(imported)
                    logger.success("Loaded plugin %s", full_name)
                else:
                    logger.error("Plugin %s missing handle()", full_name)
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to import %s: %s", full_name, exc)

    def dispatch(
        self, command: str, params: List[str], context: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        for module in self.modules:
            try:
                result = module.handle(command, params, context, self.settings)
            except Exception as exc:  # pragma: no cover
                logger.error("Plugin %s crashed: %s", module.__name__, exc)
                continue
            if result:
                logger.success("Plugin %s handled command %s", module.__name__, command)
                return result
        logger.info("No plugin handled command %s", command)
        return None

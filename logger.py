import logging
from typing import Any

SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def _configure_root_logger() -> logging.Logger:
    logger = logging.getLogger("bot")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class BotLogger:
    """Simple logger wrapper exposing info/success/error helpers."""

    def __init__(self) -> None:
        self._logger = _configure_root_logger()

    def info(self, message: str, *args: Any) -> None:
        self._logger.info(message, *args)

    def success(self, message: str, *args: Any) -> None:
        self._logger.log(SUCCESS_LEVEL, message, *args)

    def error(self, message: str, *args: Any) -> None:
        self._logger.error(message, *args)


logger = BotLogger()

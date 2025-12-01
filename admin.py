from __future__ import annotations

from typing import Any, Dict, List

from logger import logger


class AdminHandler:
    """Processes commands reserved for super administrators."""

    def __init__(self) -> None:
        self._commands = {
            "ping": self._ping,
            "status": self._status,
        }

    def handle(self, params: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not params:
            logger.error("Admin command invoked without sub-command")
            return [self._make_text_response(context, "Missing admin sub-command")] 

        sub_command = params[0].lower()
        handler = self._commands.get(sub_command, self._unknown)
        logger.info("Admin sub-command resolved: %s", sub_command)
        return handler(params[1:], context)

    def _ping(self, _: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [self._make_text_response(context, "pong")]

    def _status(self, _: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        details = f"source={context.get('source')} group={context.get('group_id')} user={context.get('user_id')}"
        return [self._make_text_response(context, f"bot online ({details})")]

    def _unknown(self, params: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        attempted = params[0] if params else "unknown"
        return [
            self._make_text_response(
                context,
                f"Unknown admin command: {attempted}. Try ping/status.",
            )
        ]

    @staticmethod
    def _make_text_response(context: Dict[str, Any], text: str) -> Dict[str, Any]:
        action = "send_group_msg" if context.get("source") == "group" else "send_private_msg"
        return {"type": action, "text": text}

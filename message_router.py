from __future__ import annotations

from typing import Any, Dict, List, Tuple

from admin import AdminHandler
from logger import logger
from plugin_loader import PluginManager
from send import SendClient


class MessageRouter:
    """Routes incoming events to admin handlers or plugins."""

    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings
        self.plugins = PluginManager(settings)
        self.admin_handler = AdminHandler()
        self.sender = SendClient(settings)

    def process_event(self, event: Dict[str, Any]) -> None:
        if event.get("post_type") != "message":
            logger.info("Ignoring non-message event: %s", event.get("post_type"))
            return

        message_type = event.get("message_type")
        if message_type not in {"group", "private"}:
            logger.info("Unsupported message type: %s", message_type)
            return

        user_id = str(event.get("user_id")) if event.get("user_id") is not None else None
        group_id = str(event.get("group_id")) if message_type == "group" else None
        if not user_id:
            logger.error("Event missing user_id: %s", event)
            return

        if not self._is_allowed(message_type, group_id or user_id):
            logger.info("Sender %s not authorized for %s", user_id, message_type)
            return

        raw_message = event.get("raw_message")
        if not raw_message:
            raw_message = self._message_to_text(event.get("message"))
        raw_message = (raw_message or "").strip()
        parsed = self._parse_command(raw_message)
        if not parsed:
            logger.info("Message filtered because prefix did not match .bot/。bot")
            return

        command, params = parsed
        logger.info("Command parsed: %s params=%s", command, params)

        context = {
            "source": message_type,
            "group_id": group_id,
            "user_id": user_id,
            "params": params,
            "settings": self.settings,
        }

        responses: List[Dict[str, Any]] | None
        if command == "admin":
            responses = self._handle_admin(params, context)
        else:
            responses = self.plugins.dispatch(command, params, context)

        if responses:
            self.sender.dispatch(responses, context)
        else:
            logger.info("No responses generated for command %s", command)

    def _handle_admin(self, params: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        user_id = context.get("user_id")
        supers = {str(uid) for uid in self.settings.get("superadmin", [])}
        if user_id not in supers:
            logger.info("Unauthorized admin attempt from %s", user_id)
            return [
                {
                    "type": "send_private_msg",
                    "number": user_id,
                    "text": "You are not authorized to use admin commands.",
                }
            ]
        return self.admin_handler.handle(params, context)

    def _is_allowed(self, source: str, identifier: str) -> bool:
        if source == "group":
            return self._evaluate_list(self.settings.get("group", []), identifier)
        return self._evaluate_list(self.settings.get("private", []), identifier)

    @staticmethod
    def _evaluate_list(rules: List[str], identifier: str) -> bool:
        if not identifier:
            return False
        identifier = str(identifier)
        normalized = [str(item) for item in rules]
        if not normalized:
            return False
        if normalized == ["all"]:
            return True
        if "all" in normalized:
            blacklist = {item for item in normalized if item != "all"}
            return identifier not in blacklist
        return identifier in normalized

    @staticmethod
    def _parse_command(message: str) -> Tuple[str, List[str]] | None:
        if not message:
            return None
        prefixes = (".bot", "。bot")
        lowered = message.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix):
                trimmed = message[len(prefix) :].strip()
                if not trimmed:
                    return None
                parts = trimmed.split()
                if not parts:
                    return None
                command = parts[0].lower()
                params = parts[1:]
                return command, params
        return None

    @staticmethod
    def _message_to_text(message_segments: Any) -> str:
        if not isinstance(message_segments, list):
            return ""
        texts: List[str] = []
        for segment in message_segments:
            if not isinstance(segment, dict):
                continue
            if segment.get("type") == "text":
                data = segment.get("data") or {}
                texts.append(str(data.get("text", "")))
        return "".join(texts)

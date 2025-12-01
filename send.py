from __future__ import annotations

import json
from typing import Any, Dict, Iterable

import requests

from logger import logger


class SendClient:
    """Simple HTTP client used to send actions back to OneBot."""

    def __init__(self, settings: Dict[str, Any]) -> None:
        ip = settings["ip"]
        port = settings["send"]
        self.base_url = f"http://{ip}:{port}"
        logger.info("Send client initialized for %s", self.base_url)

    def dispatch(self, responses: Iterable[Dict[str, Any]], context: Dict[str, Any]) -> None:
        for response in responses:
            action = response.get("type")
            if not action:
                logger.error("Response entry missing action type: %s", response)
                continue

            payload = response.get("payload")
            if payload:
                self._post(action, payload)
                continue

            text = response.get("text", "")
            number = response.get("number")
            payload = self._build_text_payload(action, text, number, context)
            if not payload:
                continue
            self._post(action, payload)

    def _post(self, action: str, payload: Dict[str, Any]) -> None:
        url = f"{self.base_url}/{action}"
        try:
            logger.info("POST %s -> %s", action, json.dumps(payload, ensure_ascii=False))
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.success("Action %s sent successfully", action)
        except requests.RequestException as exc:
            logger.error("Failed to call %s: %s", action, exc)

    @staticmethod
    def _build_text_payload(
        action: str, text: str, number: str | None, context: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        message = [{"type": "text", "data": {"text": text}}]
        source = context.get("source")
        group_id = context.get("group_id")
        user_id = context.get("user_id")

        if action == "send_private_msg":
            target = number or user_id
            if not target:
                logger.error("Missing user id for private message")
                return None
            return {"user_id": target, "message": message}

        if action == "send_group_msg":
            target = number or group_id
            if not target:
                logger.error("Missing group id for group message")
                return None
            return {"group_id": target, "message": message}

        if action == "send_msg":
            payload: Dict[str, Any] = {"message_type": source or "private", "message": message}
            target_value = number
            if source == "group":
                payload["group_id"] = target_value or group_id
            else:
                payload["user_id"] = target_value or user_id
            if (source == "group" and not payload.get("group_id")) or (
                source != "group" and not payload.get("user_id")
            ):
                logger.error("Missing target identifier for send_msg action")
                return None
            return payload

        logger.error("Unsupported action for automatic payload creation: %s", action)
        return None

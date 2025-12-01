from __future__ import annotations

from queue import Queue
from typing import Any, Dict

from flask import Flask, jsonify, request

from logger import logger


def create_listener_app(message_queue: Queue, settings: Dict[str, Any]) -> Flask:
    app = Flask(__name__)

    @app.route("/", methods=["POST"])
    def receive_event() -> tuple[str, int]:
        event = request.get_json(force=True, silent=True)
        if not isinstance(event, dict):
            logger.error("Invalid event payload: %s", event)
            return "ignored", 400

        logger.info("Event received: post_type=%s", event.get("post_type"))
        message_queue.put(event)
        return "OK", 200

    @app.route("/health", methods=["GET"])
    def health_check() -> Any:
        return jsonify({"status": "ok", "workers": settings.get("workers", 0)})

    return app

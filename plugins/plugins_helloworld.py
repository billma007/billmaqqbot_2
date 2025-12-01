from __future__ import annotations

from typing import Any, Dict, List


def handle(
    command: str, params: List[str], context: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]] | None:
    if command != "hello":
        return None

    lower_params = [param.lower() for param in params]
    if lower_params[:2] == ["world", "too!"]:
        text = "hello world!"
    else:
        joined = " ".join(params) if params else "there"
        text = f"hello {joined}!"

    action = "send_group_msg" if context.get("source") == "group" else "send_private_msg"
    response = {
        "type": action,
        "number": context.get("group_id") if action == "send_group_msg" else context.get("user_id"),
        "text": text,
    }
    return [response]

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

TEST_FILE = Path(__file__).resolve().parent.parent / "test1.docx"


def handle(
    command: str, params: List[str], context: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]] | None:
    if command != "test" or not params:
        return None

    first_param = params[0].lower()
    if first_param != "1":
        return None

    # Provide a simple fallback if the requested attachment is missing.
    if not TEST_FILE.exists():
        action = "send_group_msg" if context.get("source") == "group" else "send_private_msg"
        target_number = context.get("group_id") if action == "send_group_msg" else context.get("user_id")
        if not target_number:
            return None
        return [
            {
                "type": action,
                "number": target_number,
                "text": "测试文件 test1.docx 不存在，无法发送。",
            }
        ]

    source = context.get("source")
    if source == "group":
        target = context.get("group_id")
        action = "upload_group_file"
        payload_key = "group_id"
    else:
        target = context.get("user_id")
        action = "upload_private_file"
        payload_key = "user_id"

    if not target:
        return None

    payload = {
        payload_key: target,
        "file": str(TEST_FILE),
        "name": TEST_FILE.name,
    }

    return [
        {
            "type": action,
            "payload": payload,
        }
    ]

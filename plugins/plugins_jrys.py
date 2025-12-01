from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "jrys_data.json"
FORTUNE_BUCKETS = [
    (20, "大凶！"),
    (40, "小凶！"),
    (60, "平平！"),
    (80, "小吉！"),
    (100, "大吉！"),
]


def handle(
    command: str, params: List[str], context: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]] | None:
    if command != "jrys":
        return None

    user_id = context.get("user_id")
    if not user_id:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    data = _load_data()
    day_record = data.setdefault(today, {})
    stored_value = day_record.get(str(user_id))

    if stored_value is not None:
        value = stored_value
        text_prefix = "今日运势已抽取"
    else:
        value = random.randint(0, 100)
        day_record[str(user_id)] = value
        _save_data(data)
        text_prefix = "今日运势"

    fortune_text = _fortune_text(value)
    message_text = f"{text_prefix}：{value}（{fortune_text}）"

    action = "send_group_msg" if context.get("source") == "group" else "send_private_msg"
    target_number = context.get("group_id") if action == "send_group_msg" else context.get("user_id")
    if not target_number:
        return None

    return [
        {
            "type": action,
            "number": target_number,
            "text": message_text,
        }
    ]


def _load_data() -> Dict[str, Dict[str, int]]:
    if not DATA_FILE.exists():
        return {}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_data(data: Dict[str, Dict[str, int]]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _fortune_text(value: int) -> str:
    for upper, description in FORTUNE_BUCKETS:
        if value <= upper:
            return description
    return FORTUNE_BUCKETS[-1][1]

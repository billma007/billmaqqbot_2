from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List

from logger import logger

COMMAND_ALIASES = {"gpb", "bullshit", "gpbt", "狗屁不通", "狗屁不通生成器"}
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "goupibutongdata.json"

DUPLICATION_FACTOR = 2
MAX_LENGTH = 6000
PARAGRAPH_THRESHOLD = 5
QUOTE_THRESHOLD = 20

_sys_random = random.SystemRandom()
_templates: Dict[str, List[str]] | None = None
_bosh_iter: Iterator[str] | None = None
_famous_iter: Iterator[str] | None = None


def handle(
    command: str, params: List[str], context: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]] | None:
    if command not in COMMAND_ALIASES:
        return None

    if not params:
        return _text_response(context, "请提供生成主题，例如 `.bot gpb 人生意义`。")

    topic = " ".join(params)
    data = _load_templates()
    if not data:
        return _text_response(context, "模板数据加载失败，请检查 data/goupibutongdata.json。")

    _ensure_generators(data)
    article = _build_article(topic)
    return _forward_response(context, _split_paragraphs(article))


def _build_article(topic: str) -> str:
    buffer: List[str] = []
    while len("".join(buffer)) < MAX_LENGTH:
        branch = _sys_random.randint(0, 100)
        if branch < PARAGRAPH_THRESHOLD:
            buffer.append(_new_paragraph())
        elif branch < QUOTE_THRESHOLD:
            buffer.append(_famous_quote())
        else:
            buffer.append(_next_bosh())
    content = "".join(buffer)
    return content.replace("x", topic)


def _next_bosh() -> str:
    if _bosh_iter is None:
        return ""
    return next(_bosh_iter)


def _famous_quote() -> str:
    if _templates is None or _famous_iter is None:
        return ""
    sentence = next(_famous_iter)
    before = _sys_random.choice(_templates.get("before", ["曾经说过"]))
    after = _sys_random.choice(_templates.get("after", ["这启发了我。"]))
    sentence = sentence.replace("a", before, 1)
    sentence = sentence.replace("b", after, 1)
    return sentence


def _new_paragraph() -> str:
    return ". \r\n    "


def _split_paragraphs(article: str) -> List[str]:
    lines = article.split("\r\n")
    paragraphs: List[str] = []
    current: List[str] = []
    for line in lines:
        if not line.strip():
            if current:
                paragraphs.append("\r\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("\r\n".join(current))
    return paragraphs or [article]


def _ensure_generators(data: Dict[str, List[str]]) -> None:
    global _bosh_iter, _famous_iter
    if _bosh_iter is None:
        _bosh_iter = _shuffle_cycle(data.get("bosh", []))
    if _famous_iter is None:
        _famous_iter = _shuffle_cycle(data.get("famous", []))


def _shuffle_cycle(items: Iterable[str]) -> Iterator[str]:
    pool = list(items) * DUPLICATION_FACTOR
    if not pool:
        pool = [""]
    while True:
        _sys_random.shuffle(pool)
        for entry in pool:
            yield entry


def _load_templates() -> Dict[str, List[str]]:
    global _templates
    if _templates is not None:
        return _templates
    if not DATA_FILE.exists():
        logger.error("goupibutong data file missing: %s", DATA_FILE)
        _templates = {}
        return _templates
    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            _templates = json.load(handle)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse %s: %s", DATA_FILE, exc)
        _templates = {}
    return _templates


def _text_response(context: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    action = "send_group_msg" if context.get("source") == "group" else "send_private_msg"
    target = context.get("group_id") if action == "send_group_msg" else context.get("user_id")
    if not target:
        return []
    normalized = text.replace("\n", "\r\n")
    return [
        {
            "type": action,
            "number": target,
            "text": normalized,
        }
    ]


def _forward_response(context: Dict[str, Any], paragraphs: List[str]) -> List[Dict[str, Any]]:
    if not paragraphs:
        return _text_response(context, "暂时生成不了内容，请稍后再试。")

    nickname = "狗屁不通生成器"
    user_id = str(context.get("user_id")) or "0"
    nodes = []
    for paragraph in paragraphs:
        content = [
            {
                "type": "text",
                "data": {"text": paragraph.replace("\n", "\r\n")},
            }
        ]
        nodes.append(
            {
                "type": "node",
                "data": {
                    "user_id": user_id,
                    "nickname": nickname,
                    "content": content,
                },
            }
        )

    if context.get("source") == "group":
        return [
            {
                "type": "send_group_forward_msg",
                "payload": {"group_id": context.get("group_id"), "messages": nodes},
            }
        ]
    return [
        {
            "type": "send_private_forward_msg",
            "payload": {"user_id": context.get("user_id"), "messages": nodes},
        }
    ]

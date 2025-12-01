from __future__ import annotations

import json
from typing import Any, Dict, List

import requests

API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TEMPERATURE = 0.7


def handle(
    command: str, params: List[str], context: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]] | None:
    if command != "chat":
        return None

    prompt = " ".join(params).strip()
    if not prompt:
        return _build_text_response(context, "请在 .bot chat 后输入需要向 DeepSeek 提问的内容。")

    deepseek_config = settings.get("deepseek") or {}
    if not deepseek_config.get("enabled"):
        return _build_text_response(context, "DeepSeek 功能未启用，请在 settings.json 中开启。")

    api_key = deepseek_config.get("api_key")
    if not api_key:
        return _build_text_response(context, "DeepSeek API Key 未配置，无法继续。")

    model = deepseek_config.get("model", DEFAULT_MODEL)
    temperature = deepseek_config.get("temperature", DEFAULT_TEMPERATURE)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": deepseek_config.get("system_prompt", "你是一个乐于助人的聊天助手。")},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        data = response.json()
        message = _extract_message(data)
    except requests.RequestException as exc:
        message = f"DeepSeek API 请求失败：{exc}"
    except (ValueError, KeyError) as exc:
        message = f"DeepSeek 返回结果解析失败：{exc}"

    return _build_text_response(context, message)


def _extract_message(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not choices:
        return "DeepSeek 没有返回任何内容。"
    message = choices[0].get("message", {}).get("content", "").strip()
    return message or "DeepSeek 没有返回任何内容。"


def _build_text_response(context: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    action = "send_group_msg" if context.get("source") == "group" else "send_private_msg"
    number = context.get("group_id") if action == "send_group_msg" else context.get("user_id")
    if not number:
        return []
    return [
        {
            "type": action,
            "number": number,
            "text": text,
        }
    ]

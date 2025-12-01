from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List

from logger import logger
from plugins.restart_engine import HandlerException, Life

COMMAND_ALIASES = {"restart", "liferestart", "人生重开", "人生重来"}
START_ALIASES = {"start", "begin", "开始", "重开"}
PICK_ALIASES = {"pick", "选择", "选"}
ALLOC_ALIASES = {"alloc", "allocate", "attrs", "point", "points", "加点", "属性"}
STATUS_ALIASES = {"status", "state", "进度"}
END_ALIASES = {"end", "cancel", "stop", "退出", "结束"}
RANDOM_ALIASES = {"random", "auto", "随机"}

ATTR_ALIASES = {
    "chr": "CHR",
    "颜值": "CHR",
    "int": "INT",
    "智力": "INT",
    "str": "STR",
    "体质": "STR",
    "mny": "MNY",
    "家境": "MNY",
}
ATTR_ORDER = ["CHR", "INT", "STR", "MNY"]
MAX_ATTR_PER_STAT = 10
FORWARD_THRESHOLD = 10
LINES_PER_NODE = 4

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "restart"
STATE_FILE = DATA_DIR / "restart.json"

_engine_ready = False
try:
    Life.load(str(DATA_DIR))
    _engine_ready = True
except FileNotFoundError as exc:  # pragma: no cover - missing assets surfaced at runtime
    logger.error("Failed to load restart assets: %s", exc)

_sys_random = random.SystemRandom()


def handle(
    command: str, params: List[str], context: Dict[str, Any], settings: Dict[str, Any]
) -> List[Dict[str, Any]] | None:
    if command not in COMMAND_ALIASES:
        return None

    if not _engine_ready:
        return _text_response(context, "人生重开数据未准备就绪，请检查 data/restart 目录。")

    sub = params[0].lower() if params else "start"
    if sub in PICK_ALIASES:
        return _handle_pick(context, params[1:])
    if sub in ALLOC_ALIASES:
        return _handle_allocate(context, params[1:])
    if sub in RANDOM_ALIASES:
        return _handle_random(context)
    if sub in STATUS_ALIASES:
        return _handle_status(context)
    if sub in END_ALIASES:
        return _handle_cancel(context)
    if sub in START_ALIASES or not params:
        return _handle_start(context)
    # 无法识别子命令时默认重新开始
    return _handle_start(context)


def _handle_start(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    state = _load_state()
    key = _session_key(context)
    seed = _sys_random.randint(1, 2**31 - 1)
    options = _generate_talent_options(seed)
    state[key] = {
        "seed": seed,
        "stage": "talent",
        "options": options,
        "selected": [],
    }
    _save_state(state)

    lines = ["🎲 人生重开已准备，请从以下天赋中任选 3 个："]
    for idx, talent in enumerate(options, start=1):
        grade = _grade_label(talent["grade"])
        lines.append(f"{idx}. {talent['name']}（{grade}）- {talent['description']}")
    lines.append("使用 `.bot restart pick 1 3 5` 这样格式挑选天赋。")
    lines.append("若想直接体验一把，可发送 `.bot restart random` 进行全随机重开。")
    return _text_response(context, "\n".join(lines))


def _handle_pick(context: Dict[str, Any], args: List[str]) -> List[Dict[str, Any]]:
    state = _load_state()
    key = _session_key(context)
    session = state.get(key)
    if not session or session.get("stage") != "talent":
        return _text_response(context, "当前没有等待选天赋的进度，可先 `.bot restart` 重开。")
    if not args:
        return _text_response(context, "请在 pick 后输入 3 个序号，例如 `.bot restart pick 1 2 3`。")

    try:
        indexes = sorted({int(item) for item in args})
    except ValueError:
        return _text_response(context, "天赋序号应为整数。")

    if len(indexes) != 3:
        return _text_response(context, "需要正好选择 3 个天赋。")

    options = session["options"]
    if min(indexes) < 1 or max(indexes) > len(options):
        return _text_response(context, "天赋序号超出范围，请重新确认。")

    selected_ids = [options[i - 1]["id"] for i in indexes]
    session["selected"] = selected_ids
    session["stage"] = "allocate"
    state[key] = session

    try:
        available = _calculate_available_points(session)
    except HandlerException as exc:
        logger.error("Failed to compute restart property pool: %s", exc)
        return _text_response(context, "内部错误：属性点计算失败，请重试 `.bot restart`。")

    _save_state(state)
    picked = ", ".join(options[i - 1]["name"] for i in indexes)
    msg = (
        f"已选择天赋：{picked}\n"
        f"可分配属性点：{available}，单项最多 {MAX_ATTR_PER_STAT} 点。\n"
        "可使用 `.bot restart alloc 6 6 4 4` 或 `.bot restart alloc 颜值=6 智力=6 体质=4 家境=4` 进行加点"
    )
    return _text_response(context, msg)


def _handle_allocate(context: Dict[str, Any], args: List[str]) -> List[Dict[str, Any]]:
    state = _load_state()
    key = _session_key(context)
    session = state.get(key)
    if not session or session.get("stage") != "allocate":
        return _text_response(context, "请先选择天赋后再加点。")
    if not args:
        return _text_response(
            context,
            "请提供属性分配，例如 `.bot restart alloc 6 6 4 4` 或 `.bot restart alloc 颜值=5 智力=5 体质=5 家境=5`。",
        )

    try:
        life = _build_life(session)
    except HandlerException as exc:
        logger.error("Failed to build life for allocation: %s", exc)
        return _text_response(context, "内部错误：无法恢复天赋，请重新 `.bot restart`。")

    available = max(life.property.total, 0)
    allocation, error = _parse_allocation(args)
    if error:
        return _text_response(context, error)
    total_used = sum(allocation.values())
    if total_used != available:
        return _text_response(context, f"当前可用 {available} 点，实际分配 {total_used} 点，请重新调整。")

    life.property.apply(allocation)
    try:
        logs = _run_simulation(life, session)
    except HandlerException:
        return _text_response(context, "模拟过程中出现异常，请 `.bot restart` 重新开始。")

    state.pop(key, None)
    _save_state(state)
    return _format_log_response(logs, context)


def _handle_random(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    seed = _sys_random.randint(1, 2**31 - 1)
    options = _generate_talent_options(seed)
    if len(options) < 3:
        return _text_response(context, "随机天赋生成失败，请稍后再试。")

    indexes = sorted(_sys_random.sample(range(len(options)), 3))
    selected_ids = [options[i]["id"] for i in indexes]
    session = {"seed": seed, "selected": selected_ids, "options": options}

    try:
        life = _build_life(session)
    except HandlerException as exc:
        logger.error("Failed to build life for random run: %s", exc)
        return _text_response(context, "内部错误：随机重开失败，请稍后再试。")

    available = max(life.property.total, 0)
    try:
        allocation = _random_allocation(available)
    except ValueError as exc:
        logger.error("Random allocation failed: %s", exc)
        return _text_response(context, "内部错误：随机加点失败，请稍后再试。")

    life.property.apply(allocation)
    try:
        logs = _run_simulation(life, session)
    except HandlerException:
        return _text_response(context, "模拟过程中出现异常，请稍后再试。")

    intro = []
    names = _talent_names(session, selected_ids)
    if names:
        intro.append(f"🎲 随机天赋：{', '.join(names)}")
    intro.append(
        "随机加点："
        f"颜{allocation['CHR']} 智{allocation['INT']} 体{allocation['STR']} 家{allocation['MNY']}"
    )
    return _format_log_response(intro + logs, context)


def _handle_status(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    session = _load_state().get(_session_key(context))
    if not session:
        return _text_response(context, "当前没有进行中的人生重开，发送 `.bot restart` 即可开始。")
    stage = session.get("stage")
    if stage == "talent":
        return _text_response(context, "等待选择天赋，使用 `.bot restart pick ...`。")
    if stage == "allocate":
        return _text_response(context, "等待属性分配，使用 `.bot restart alloc ...`。")
    return _text_response(context, "进度状态异常，请重新 `.bot restart`。")


def _handle_cancel(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    state = _load_state()
    key = _session_key(context)
    if key in state:
        state.pop(key)
        _save_state(state)
        return _text_response(context, "已清除当前人生重开进度。")
    return _text_response(context, "没有可取消的进度。")


def _run_simulation(life: Life, session: Dict[str, Any]) -> List[str]:
    logs: List[str] = []
    try:
        for day in life.run():
            if not day:
                continue
            prefix = day[0]
            extras = [piece for piece in day[1:] if piece]
            line = prefix if not extras else f"{prefix} {'；'.join(extras)}"
            logs.append(line)
    except Exception as exc:  # pragma: no cover - engine level exceptions are surfaced to user
        logger.error("Life simulation failed: %s", exc)
        raise HandlerException("simulation failed") from exc

    chosen = session.get("selected", [])
    talent_names = _talent_names(session, chosen)
    if talent_names:
        logs.append(f"继承天赋：{', '.join(talent_names)}")
    logs.append(str(life.property))
    logs.append("本次人生已结束，可再次 `.bot restart` 继续重开。")
    return logs


def _talent_names(session: Dict[str, Any], ids: List[int]) -> List[str]:
    names = []
    id_to_info = {talent["id"]: talent["name"] for talent in session.get("options", [])}
    for tid in ids:
        name = id_to_info.get(tid)
        if name:
            names.append(name)
    return names


def _format_log_response(lines: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not lines:
        return _text_response(context, "没有产生任何事件，请重新重开一次吧。")
    if len(lines) <= FORWARD_THRESHOLD:
        return _text_response(context, "\n".join(lines))

    nodes = _build_forward_nodes(lines, context)
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


def _build_forward_nodes(lines: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    chunk: List[Dict[str, Any]] = []
    nickname = "人生重开"
    user_id = str(context.get("user_id"))

    for line in lines:
        chunk.append({"type": "text", "data": {"text": line + '\n'}})
        if len(chunk) >= LINES_PER_NODE:
            nodes.append(_make_node(chunk, nickname, user_id))
            chunk = []
    if chunk:
        nodes.append(_make_node(chunk, nickname, user_id))
    return nodes


def _make_node(content: List[Dict[str, Any]], nickname: str, user_id: str) -> Dict[str, Any]:
    return {
        "type": "node",
        "data": {
            "user_id": user_id,
            "nickname": nickname,
            "content": content,
        },
    }


def _parse_allocation(tokens: List[str]) -> tuple[Dict[str, int], str | None]:
    allocation = {key: 0 for key in ATTR_ORDER}
    if not tokens:
        return allocation, "请提供属性分配。"

    if all("=" not in token for token in tokens):
        if len(tokens) != len(ATTR_ORDER):
            return allocation, "简写模式需依次输入 4 个数字，例如 `6 6 4 4`。"
        try:
            values = [int(token) for token in tokens]
        except ValueError:
            return allocation, "属性值必须是整数。"
        for idx, key in enumerate(ATTR_ORDER):
            value = values[idx]
            if value < 0 or value > MAX_ATTR_PER_STAT:
                return allocation, f"{key} 取值需在 0~{MAX_ATTR_PER_STAT} 之间。"
            allocation[key] = value
        return allocation, None

    for token in tokens:
        if "=" not in token:
            return allocation, "请统一使用简写模式或 键=值 模式。"
        raw_key, raw_value = token.split("=", 1)
        key = ATTR_ALIASES.get(raw_key.strip().lower(), raw_key.strip().upper())
        if key not in allocation:
            return allocation, f"未知的属性：{raw_key}"
        try:
            value = int(raw_value)
        except ValueError:
            return allocation, f"属性值必须是整数：{raw_value}"
        if value < 0 or value > MAX_ATTR_PER_STAT:
            return allocation, f"{key} 取值需在 0~{MAX_ATTR_PER_STAT} 之间。"
        allocation[key] = value
    return allocation, None


def _random_allocation(total: int) -> Dict[str, int]:
    capacity = MAX_ATTR_PER_STAT * len(ATTR_ORDER)
    if total > capacity:
        raise ValueError("property pool exceeds allocation capacity")
    allocation = {key: 0 for key in ATTR_ORDER}
    remaining = total
    while remaining > 0:
        candidates = [key for key in ATTR_ORDER if allocation[key] < MAX_ATTR_PER_STAT]
        if not candidates:
            raise ValueError("no candidates available for random allocation")
        selected = _sys_random.choice(candidates)
        allocation[selected] += 1
        remaining -= 1
    return allocation


def _build_life(session: Dict[str, Any]) -> Life:
    seed = session["seed"]
    selected = session.get("selected", [])
    rnd = random.Random(seed)
    life = Life(rnd)
    talents = list(life.talent.genTalents(life._talent_randomized))
    id_map = {talent.id: talent for talent in talents}
    try:
        chosen = [id_map[tid] for tid in selected]
    except KeyError as exc:
        raise HandlerException("selected talent mismatch") from exc
    for talent in chosen:
        life.talent.addTalent(talent)
    life.talent.updateTalentProp()
    return life


def _calculate_available_points(session: Dict[str, Any]) -> int:
    life = _build_life(session)
    return max(life.property.total, 0)


def _generate_talent_options(seed: int) -> List[Dict[str, Any]]:
    rnd = random.Random(seed)
    life = Life(rnd)
    talents = list(life.talent.genTalents(life._talent_randomized))
    options = []
    for talent in talents:
        options.append(
            {
                "id": talent.id,
                "name": talent.name,
                "description": talent.desc,
                "grade": talent.grade,
            }
        )
    return options


def _grade_label(grade: int) -> str:
    return {0: "普通", 1: "优秀", 2: "稀有", 3: "传说"}.get(grade, "未知")


def _session_key(context: Dict[str, Any]) -> str:
    user_id = str(context.get("user_id"))
    if context.get("source") == "group":
        return f"group:{context.get('group_id')}:{user_id}"
    return f"private:{user_id}"


def _text_response(context: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    normalized = text.replace("\n", "\r\n")
    action = "send_group_msg" if context.get("source") == "group" else "send_private_msg"
    target = context.get("group_id") if action == "send_group_msg" else context.get("user_id")
    if not target:
        return []
    return [
        {
            "type": action,
            "number": target,
            "text": normalized,
        }
    ]


def _load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text("{}", encoding="utf-8")
    try:
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        logger.error("restart.json 损坏，已重置为空。")
        STATE_FILE.write_text("{}", encoding="utf-8")
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)

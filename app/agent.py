from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.llama_client import llama_client
from app.todo_tools import ToolResult, repo


class AgentState(TypedDict, total=False):
    user_message: str
    image_path: str | None
    normalized_message: str
    vision_summary: str | None
    intent: str
    action_args: dict[str, Any]
    tool_result: dict[str, Any] | None
    assistant_message: str
    chat_title: str
    needs_clarification: bool
    clarification_message: str
    parse_error: str | None


INTENTS = {"create", "list", "get", "update", "delete", "done", "reopen", "search", "chat"}
TIME_HINT_PATTERNS = [
    r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}",
    r"\d{1,2}:\d{2}(?::\d{2})?",
    r"\d+\s*(分钟|小时|天)[前后]",
]
TIME_HINT_KEYWORDS = {
    "现在",
    "刚刚",
    "此刻",
    "今天",
    "昨天",
    "明天",
    "今早",
    "今天早上",
    "今天上午",
    "今天中午",
    "今天下午",
    "今天晚上",
    "今晚",
    "昨晚",
    "明早",
    "明晚",
    "上午",
    "中午",
    "下午",
    "晚上",
}
SEARCH_TRIGGER_WORDS = {"搜索", "查找", "查询", "检索"}
SEARCH_CONTEXT_WORDS = {"待办", "任务", "事项"}


def prepare_input(state: AgentState) -> AgentState:
    message = state["user_message"].strip()
    return {"normalized_message": message, "vision_summary": None}


def vision_understanding(state: AgentState) -> AgentState:
    image_path = state.get("image_path")
    if not image_path:
        return {}
    summary = llama_client.chat(
        system_prompt="你是图片任务提取助手。请简要总结图片中与待办事项相关的信息，使用中文，一段话，不要编造。",
        user_prompt="请阅读这张图片，提取其中可能与任务、提醒、待办、时间安排相关的信息。",
        image_path=Path(image_path),
        temperature=0.1,
        max_tokens=200,
    )
    return {"vision_summary": summary}


def intent_router(state: AgentState) -> AgentState:
    fallback = heuristic_route(state["normalized_message"], state.get("vision_summary"))
    system_prompt = """
你是 Todo 指令路由器。你的职责是理解用户真实意图，并输出可执行 JSON。

请把用户请求识别为一个 todo 操作，并只返回 JSON。

允许的 intent:
- create
- list
- get
- update
- delete
- done
- reopen
- search
- chat

返回格式:
{
  "intent": "done",
  "title": "",
  "task_id": 0,
  "task_ids": [],
  "status": "",
  "query": "",
  "created_at": "",
  "completed_at": "",
  "title_update": "",
  "reason": "一句中文说明"
}

规则:
1. 如果用户是在新增任务，intent 用 create。
2. 如果用户只是聊天、寒暄、闲聊、询问能力，intent 用 chat。
3. 如果有图片且用户要求提取、识别、加入待办，通常是 create。
4. 用户表达“完成了/标记完成/搞定了”时，intent 必须是 done，不要输出 update。
5. 用户表达“重新打开/恢复”时，intent 必须是 reopen。
6. task_id 不存在时返回 0。
7. 如果用户一次提到多个任务编号，请把所有编号都放进 task_ids，例如 [11,12]。
8. 只返回 JSON，不要额外解释，不要输出 Markdown 代码块，不要输出额外前缀。
9. `created_at` 和 `completed_at` 只有在用户文本里明确提到对应时间时才能返回；如果用户没有提时间，必须返回空字符串。
10. 不允许根据常识、图片、任务内容自行编造时间。
11. “创建时间”“开始时间”“于某时创建”“在某时添加” 都表示 `created_at`。
12. “完成时间”“于某时完成”“在某时完成”“某时已完成” 都表示 `completed_at`。
13. 像“添加待办-这是一个测试任务创建时间为2026年3月15日17点23分32秒”这种句子，intent 必须是 `create`，title 是任务标题，`created_at` 是 `2026-03-15 17:23:32`。
14. 像“#16任务完成时间为2026年3月16日20点30分00秒”这种句子，intent 必须是 `done`，`task_id` 是 16，`completed_at` 是 `2026-03-16 20:30:00`。
15. 像“查一下运营监控相关的未完成待办事项”这种句子，intent 应该是 `search`，`query` 是 `运营监控`，`status` 是 `pending`。
	""".strip()
    user_prompt = f"""
用户文本:
{state["normalized_message"]}

图片摘要:
{state.get("vision_summary") or "无"}
""".strip()

    try:
        response = llama_client.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=1000,
        )
        parsed = llama_client.extract_json_block(response)
    except Exception:
        return {
            "intent": "chat",
            "action_args": {
                "intent": "chat",
                "title": "",
                "task_id": 0,
                "task_ids": [],
                "status": "",
                "query": "",
                "created_at": "",
                "completed_at": "",
                "title_update": "",
                "reason": "",
            },
            "needs_clarification": True,
            "clarification_message": "模型响应内容无法解析，请重试。",
            "parse_error": "模型响应内容无法解析，请重试。",
        }

    normalized = normalize_action_args(parsed)
    intent = str(normalized.get("intent") or "chat")
    if intent not in INTENTS:
        normalized = fallback
        intent = str(normalized.get("intent") or "chat")

    validated, should_fallback = validate_action_args(
        normalized,
        original_message=state["normalized_message"],
    )
    if intent == "chat" and str(fallback.get("intent") or "chat") != "chat":
        should_fallback = True
    if should_fallback:
        fallback_normalized = normalize_action_args(fallback)
        if should_clarify(validated, fallback_normalized):
            return {
                "intent": "chat",
                "action_args": validated,
                "needs_clarification": True,
                "clarification_message": build_clarification_message(validated, state["normalized_message"]),
            }
        validated = fallback_normalized
        intent = str(validated.get("intent") or "chat")
    else:
        intent = str(validated.get("intent") or "chat")

    return {"intent": intent, "action_args": validated}


def normalize_action_args(parsed: dict[str, Any] | None) -> dict[str, Any]:
    data = parsed or {}
    intent = str(data.get("intent") or "chat").strip().lower()
    status = str(data.get("status") or "").strip().lower()
    task_id_raw = data.get("task_id")
    try:
        task_id = int(task_id_raw or 0)
    except (TypeError, ValueError):
        task_id = 0
    task_ids_raw = data.get("task_ids") or []
    task_ids = normalize_task_ids(task_ids_raw)
    if not task_ids and task_id > 0:
        task_ids = [task_id]

    normalized = {
        "intent": intent if intent in INTENTS else "chat",
        "title": str(data.get("title") or "").strip(),
        "task_id": task_id,
        "task_ids": task_ids,
        "status": status if status in {"pending", "done"} else "",
        "query": str(data.get("query") or "").strip(),
        "created_at": str(data.get("created_at") or "").strip(),
        "completed_at": str(data.get("completed_at") or "").strip(),
        "title_update": str(data.get("title_update") or "").strip(),
        "reason": str(data.get("reason") or "").strip(),
    }
    return normalized


def validate_action_args(
    args: dict[str, Any],
    original_message: str,
) -> tuple[dict[str, Any], bool]:
    intent = str(args.get("intent") or "chat")
    args = sanitize_time_args(args, original_message)
    task_id = int(args.get("task_id") or 0)
    task_ids = normalize_task_ids(args.get("task_ids") or [])
    if task_ids:
        args["task_ids"] = task_ids
        if task_id <= 0:
            args["task_id"] = task_ids[0]

    if intent in {"done", "delete", "reopen", "get"} and not task_ids and task_id <= 0:
        return args, True

    if intent == "update":
        has_update_content = bool(args.get("title_update") or args.get("created_at"))
        if task_id <= 0 or not has_update_content:
            return args, True

    if intent == "create" and not args.get("title"):
        args["title"] = original_message.strip()

    if intent == "search" and not args.get("query"):
        return args, True

    if intent in {"list", "search"} and not args.get("status"):
        if "未完成" in original_message or "待处理" in original_message:
            args["status"] = "pending"
        elif "已完成" in original_message:
            args["status"] = "done"

    return args, False


def message_has_explicit_time(message: str) -> bool:
    content = message.strip()
    if not content:
        return False
    if any(keyword in content for keyword in TIME_HINT_KEYWORDS):
        return True
    return any(re.search(pattern, content) for pattern in TIME_HINT_PATTERNS)


def sanitize_time_args(args: dict[str, Any], original_message: str) -> dict[str, Any]:
    sanitized = dict(args)
    has_explicit_time = message_has_explicit_time(original_message)
    intent = str(sanitized.get("intent") or "chat")

    if intent == "create":
        sanitized["completed_at"] = ""
        if not has_explicit_time:
            sanitized["created_at"] = ""
    elif intent == "done":
        sanitized["created_at"] = ""
        if not has_explicit_time:
            sanitized["completed_at"] = ""
    elif intent == "update":
        sanitized["completed_at"] = ""
        if not has_explicit_time:
            sanitized["created_at"] = ""
    else:
        sanitized["created_at"] = ""
        sanitized["completed_at"] = ""

    return sanitized


def should_clarify(model_args: dict[str, Any], fallback_args: dict[str, Any]) -> bool:
    model_intent = str(model_args.get("intent") or "chat")
    fallback_intent = str(fallback_args.get("intent") or "chat")

    # 写操作如果模型没有给出可执行参数，不允许靠规则去猜多个任务编号。
    if model_intent in {"done", "delete", "reopen", "update", "get"}:
        return True

    # 规则和模型意图冲突时，优先澄清，避免误执行。
    if model_intent != "chat" and fallback_intent != "chat" and model_intent != fallback_intent:
        return True

    return False


def build_clarification_message(args: dict[str, Any], original_message: str) -> str:
    intent = str(args.get("intent") or "chat")
    if intent == "done":
        return (
            "我理解你是在标记任务完成，但当前没有拿到可执行的任务编号列表。\n\n"
            "请明确给我任务 ID，例如：`把 #11 和 #12 标记完成`。"
        )
    if intent == "delete":
        return "我理解你想删除任务，但当前没有拿到明确的任务编号。请直接提供任务 ID。"
    if intent == "reopen":
        return "我理解你想重新打开任务，但当前没有拿到明确的任务编号。请直接提供任务 ID。"
    if intent == "update":
        return "我理解你想修改任务，但当前缺少可执行的任务编号或修改内容。请补充任务 ID 和修改项。"
    if intent == "get":
        return "我理解你想查看任务详情，但当前没有拿到明确的任务编号。请直接提供任务 ID。"
    return f"我还不能稳定执行这条请求：{original_message}"


def heuristic_route(message: str, vision_summary: str | None) -> dict[str, Any]:
    """只做兜底，不再作为主判定逻辑。"""
    text = message.lower()
    looks_like_search = is_keyword_search_request(message)
    is_pending_query = (
        "未完成" in message
        or "待处理" in message
        or "待办" in message
        or ("还有" in message and "任务" in message)
    )
    is_done_query = "已完成" in message or "done" in text
    payload = {
        "intent": "chat",
        "title": "",
        "task_id": 0,
        "task_ids": [],
        "status": "",
        "query": "",
        "created_at": "",
        "completed_at": "",
        "title_update": "",
        "reason": "启发式兜底",
    }
    if vision_summary or any(word in message for word in ["添加", "新增", "创建", "记录", "提醒我", "加入待办", "加到待办"]):
        payload["intent"] = "create"
        payload["title"] = extract_title_for_create(message, vision_summary)
        payload["created_at"] = extract_explicit_created_time(message)
    elif (
        any(word in message for word in ["查看", "列出", "显示", "待办", "哪些", "还有"])
        or is_pending_query
        or is_done_query
    ) and not looks_like_search:
        payload["intent"] = "list"
        if is_done_query and "未完成" not in message:
            payload["status"] = "done"
        elif is_pending_query or "pending" in text:
            payload["status"] = "pending"
    elif looks_like_search:
        payload["intent"] = "search"
        payload["query"] = extract_search_query(message)
        if is_done_query and "未完成" not in message:
            payload["status"] = "done"
        elif is_pending_query or "pending" in text:
            payload["status"] = "pending"
    elif any(word in message for word in ["完成", "搞定", "done"]) and "未完成" not in message:
        payload["intent"] = "done"
        payload["completed_at"] = extract_explicit_completed_time(message)
    elif any(word in message for word in ["删除", "移除"]):
        payload["intent"] = "delete"
    elif any(word in message for word in ["重新打开", "恢复"]):
        payload["intent"] = "reopen"
    elif any(word in message for word in ["修改", "更新"]):
        payload["intent"] = "update"
        payload["task_id"] = extract_first_int(message)
        payload["title_update"] = message
    return payload


def extract_first_int(message: str) -> int:
    digits = "".join(ch if ch.isdigit() else " " for ch in message).split()
    return int(digits[0]) if digits else 0


def normalize_task_ids(value: Any) -> list[int]:
    if isinstance(value, list):
        raw_items = value
    elif value in (None, "", 0):
        raw_items = []
    else:
        raw_items = [value]
    result: list[int] = []
    for item in raw_items:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in result:
            result.append(number)
    return result


def extract_title_for_create(message: str, vision_summary: str | None) -> str:
    if vision_summary:
        return vision_summary
    cleaned = message
    cleaned = re.sub(r"^(请)?(添加|创建)(一个)?(待办|代办)[：:\-—\s]*", "", cleaned).strip()
    prefixes = [
        "请添加一个待办：",
        "请添加一个待办:",
        "请添加一个代办：",
        "请添加一个代办:",
        "添加待办：",
        "添加待办:",
        "添加代办：",
        "添加代办:",
        "请添加待办：",
        "请添加待办:",
        "请添加代办：",
        "请添加代办:",
        "创建待办：",
        "创建待办:",
        "创建代办：",
        "创建代办:",
        "请创建待办：",
        "请创建待办:",
        "请创建代办：",
        "请创建代办:",
        "请记录：",
        "请记录:",
        "提醒我",
    ]
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    time_markers = [
        "创建时间为",
        "创建时间是",
        "开始时间为",
        "开始时间是",
    ]
    for marker in time_markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip("，,：: -")
            break
    return cleaned or message


def is_keyword_search_request(message: str) -> bool:
    if any(word in message for word in SEARCH_TRIGGER_WORDS):
        return True
    if "相关" in message and any(word in message for word in SEARCH_CONTEXT_WORDS):
        return True
    if any(word in message for word in ["包含", "有关", "关于"]) and any(
        word in message for word in SEARCH_CONTEXT_WORDS
    ):
        return True
    return False


def extract_search_query(message: str) -> str:
    cleaned = message.strip()
    cleaned = re.sub(r"^(请|帮我|麻烦|我想|想|请帮我|帮忙)+", "", cleaned).strip()
    cleaned = re.sub(r"^(查一下|查下|查查|查询一下|搜索一下|搜一下|看一下|看下|看看)", "", cleaned).strip()
    cleaned = re.sub(r"^(搜索|查找|查询|检索)[：:\s]*", "", cleaned).strip()

    patterns = [
        r"(.+?)(?:相关|有关|关于)(?:的)?(?:未完成|已完成|待处理|pending|done)?(?:待办事项|待办|任务|事项)?[？?。！!]*$",
        r"(.+?)(?:未完成|已完成|待处理|pending|done)(?:的)?(?:待办事项|待办|任务|事项)?[？?。！!]*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            candidate = match.group(1).strip("：:，,。；;！？? ")
            if candidate:
                return candidate

    suffixes = [
        "相关的未完成待办事项",
        "相关的未完成待办",
        "相关的已完成待办事项",
        "相关的已完成待办",
        "相关待办事项",
        "相关待办",
        "未完成待办事项",
        "未完成待办",
        "已完成待办事项",
        "已完成待办",
        "待办事项",
        "待办",
        "任务",
        "事项",
    ]
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            candidate = cleaned[: -len(suffix)].strip("：:，,。；;！？? ")
            if candidate:
                return candidate

    return cleaned


def extract_explicit_created_time(message: str) -> str:
    patterns = [
        r"(?:创建时间|开始时间)[为是:：\s]*([0-9零一二三四五六七八九十两年月日点时分秒:\-T\/Z\+\s]+)",
        r"(?:于|在)([0-9零一二三四五六七八九十两年月日点时分秒:\-T\/Z\+\s]+)(?:创建|添加)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1).strip("，,。；; ")
    return ""


def extract_explicit_completed_time(message: str) -> str:
    patterns = [
        r"(?:完成时间)[为是:：\s]*([0-9零一二三四五六七八九十两年月日点时分秒:\-T\/Z\+\s]+)",
        r"(?:于|在)([0-9零一二三四五六七八九十两年月日点时分秒:\-T\/Z\+\s]+)(?:完成|已完成|搞定)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1).strip("，,。；; ")
    return ""


def execute_tool(state: AgentState) -> AgentState:
    intent = state["intent"]
    args = state.get("action_args", {})
    result: ToolResult
    task_ids = normalize_task_ids(args.get("task_ids") or [])

    if intent == "create":
        title = args.get("title") or state["normalized_message"]
        result = repo.create_task(title=title, created_at=args.get("created_at") or None)
    elif intent == "list":
        result = repo.list_tasks(status=args.get("status") or None)
    elif intent == "get":
        result = execute_batch_action("get", task_ids or [int(args.get("task_id") or 0)])
    elif intent == "update":
        result = repo.update_task(
            task_id=int(args.get("task_id") or 0),
            title=args.get("title_update") or None,
            created_at=args.get("created_at") or None,
        )
    elif intent == "delete":
        result = execute_batch_action("delete", task_ids or [int(args.get("task_id") or 0)])
    elif intent == "done":
        result = execute_batch_action(
            "done",
            task_ids or [int(args.get("task_id") or 0)],
            completed_at=args.get("completed_at") or None,
        )
    elif intent == "reopen":
        result = execute_batch_action("reopen", task_ids or [int(args.get("task_id") or 0)])
    elif intent == "search":
        result = repo.search_tasks(
            query=args.get("query") or state["normalized_message"],
            status=args.get("status")
        )
    else:
        result = ToolResult(True, "chat", "", {"tasks": []})

    return {
        "tool_result": {
            "ok": result.ok,
            "action": result.action,
            "message": result.message,
            "payload": result.payload or {},
        }
    }


def execute_batch_action(action: str, task_ids: list[int], **kwargs: Any) -> ToolResult:
    valid_ids = [task_id for task_id in task_ids if task_id > 0]
    if not valid_ids:
        return ToolResult(False, action, "没有解析到有效的任务编号。", {"task_ids": []})

    handlers = {
        "get": lambda task_id: repo.get_task(task_id=task_id),
        "delete": lambda task_id: repo.delete_task(task_id=task_id),
        "done": lambda task_id: repo.done_task(task_id=task_id, completed_at=kwargs.get("completed_at")),
        "reopen": lambda task_id: repo.reopen_task(task_id=task_id),
    }
    handler = handlers[action]
    results = [handler(task_id) for task_id in valid_ids]
    ok = all(item.ok for item in results)
    messages = [item.message for item in results]
    payload = {"task_ids": valid_ids, "results": [item.payload or {} for item in results]}
    prefix = {
        "get": "## 任务详情",
        "delete": "## 删除结果",
        "done": "## 完成结果",
        "reopen": "## 恢复结果",
    }[action]
    return ToolResult(ok, action, prefix + "\n\n" + "\n\n".join(f"- {message}" for message in messages), payload)


def extract_task_ids_from_payload(payload: dict[str, Any]) -> list[int]:
    task_ids: list[int] = []

    def append_task_id(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int) and value > 0 and value not in task_ids:
            task_ids.append(value)

    append_task_id(payload.get("id"))

    task = payload.get("task")
    if isinstance(task, dict):
        append_task_id(task.get("id"))

    tasks = payload.get("tasks")
    if isinstance(tasks, list):
        for item in tasks:
            if isinstance(item, dict):
                append_task_id(item.get("id"))

    raw_task_ids = payload.get("task_ids")
    if isinstance(raw_task_ids, list):
        for task_id in raw_task_ids:
            append_task_id(task_id)

    results = payload.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                append_task_id(item.get("id"))

    return task_ids


def ensure_reply_contains_task_ids(reply: str, payload: dict[str, Any]) -> str:
    task_ids = extract_task_ids_from_payload(payload)
    if not task_ids:
        return reply

    task_id_text = "、".join(str(task_id) for task_id in task_ids)
    explicit_markers = [f"任务ID：{task_id}" for task_id in task_ids]
    hash_markers = [f"#{task_id}" for task_id in task_ids]
    if any(marker in reply for marker in explicit_markers) or all(marker in reply for marker in hash_markers):
        return reply

    suffix = f"\n\n任务ID：{task_id_text}"
    return (reply.rstrip() + suffix).strip()


def write_response(state: AgentState) -> AgentState:
    if state.get("needs_clarification"):
        reply = state.get("clarification_message") or "请补充更明确的信息。"
        title = state["normalized_message"][:18] or "需要澄清"
        return {"assistant_message": reply, "chat_title": title}

    intent = state["intent"]
    tool_result = state.get("tool_result") or {}
    if intent == "chat":
        reply = llama_client.chat(
            system_prompt="你是一个中文 Todo 助手。回答简洁，明确告诉用户你能做哪些待办管理动作。",
            user_prompt=state["normalized_message"],
            temperature=0.3,
            max_tokens=300,
        )
    else:
        context = f"""
用户原始请求：
{state["normalized_message"]}

图片摘要：
{state.get("vision_summary") or "无"}

工具执行结果：
{tool_result.get("message", "")}
""".strip()
        reply = tool_result.get("message", "")
        if tool_result.get("message"):
            polished = llama_client.chat(
                system_prompt="你是一个中文 Todo 助手。请基于工具执行结果回复用户，语气直接，避免编造。如果工具结果已经足够清楚，可以原样简化复述。只要结果里出现了任务编号，就必须在回复中保留任务ID。",
                user_prompt=context,
                temperature=0.2,
                max_tokens=300,
            ).strip()
            if polished:
                reply = polished
    if not reply:
        reply = tool_result.get("message") or "这次请求已处理，但模型没有生成额外说明。"
    if intent != "chat":
        reply = ensure_reply_contains_task_ids(reply, tool_result.get("payload") or {})

    title_prompt = f"""
请为下面这轮问答生成一个不超过18个字的中文标题，只输出标题本身。

用户：
{state["normalized_message"]}

助手：
{reply}
""".strip()
    title = llama_client.chat(
        system_prompt="你是标题生成助手。",
        user_prompt=title_prompt,
        temperature=0.2,
        max_tokens=50,
    ).strip()
    title_lines = [line.strip("「」\" ") for line in title.splitlines() if line.strip()]
    safe_title = title_lines[0] if title_lines else state["normalized_message"][:18] or "未命名问答"

    return {"assistant_message": reply, "chat_title": safe_title}


def persist_chat(state: AgentState) -> AgentState:
    repo.save_chat_log(
        title=state["chat_title"],
        user_message=state["normalized_message"],
        assistant_message=state["assistant_message"],
        intent=state.get("intent"),
        image_path=state.get("image_path"),
    )
    return {}


def after_router(state: AgentState) -> Literal["execute_tool", "write_response"]:
    return "write_response" if state["intent"] == "chat" else "execute_tool"


def build_agent() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("prepare_input", prepare_input)
    graph.add_node("vision_understanding", vision_understanding)
    graph.add_node("intent_router", intent_router)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("write_response", write_response)
    graph.add_node("persist_chat", persist_chat)

    graph.add_edge(START, "prepare_input")
    graph.add_edge("prepare_input", "vision_understanding")
    graph.add_edge("vision_understanding", "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        after_router,
        {"execute_tool": "execute_tool", "write_response": "write_response"},
    )
    graph.add_edge("execute_tool", "write_response")
    graph.add_edge("write_response", "persist_chat")
    graph.add_edge("persist_chat", END)
    return graph.compile()


agent_app = build_agent()


def run_agent(user_message: str, image_path: str | None = None) -> dict[str, Any]:
    result = agent_app.invoke({"user_message": user_message, "image_path": image_path})
    return {
        "assistant_message": result["assistant_message"],
        "chat_title": result["chat_title"],
        "intent": result.get("intent"),
        "tool_result": result.get("tool_result"),
        "vision_summary": result.get("vision_summary"),
        "parse_error": result.get("parse_error"),
    }

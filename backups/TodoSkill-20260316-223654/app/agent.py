from __future__ import annotations

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


INTENTS = {"create", "list", "get", "update", "delete", "done", "reopen", "search", "chat"}


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
    heuristic = heuristic_route(state["normalized_message"], state.get("vision_summary"))
    prompt = f"""
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
{{
  "intent": "create",
  "title": "任务标题，没有则为空字符串",
  "task_id": 0,
  "status": "pending|done|",
  "query": "",
  "created_at": "",
  "completed_at": "",
  "title_update": "",
  "reason": "一句中文说明"
}}

用户文本:
{state["normalized_message"]}

图片摘要:
{state.get("vision_summary") or "无"}

规则:
1. 如果用户是在新增任务，intent 用 create。
2. 如果用户只是聊天、寒暄、闲聊、询问能力，intent 用 chat。
3. 如果有图片且用户要求提取、识别、加入待办，通常是 create。
4. task_id 不存在时返回 0。
5. 只返回 JSON，不要额外解释。
""".strip()

    response = llama_client.chat(
        system_prompt="你是 Todo 指令路由器。",
        user_prompt=prompt,
        temperature=0.1,
        max_tokens=300,
    )
    try:
        parsed = llama_client.extract_json_block(response)
    except Exception:
        parsed = heuristic
    intent = parsed.get("intent", "chat")
    if intent not in INTENTS:
        intent = "chat"
    if heuristic.get("intent") != "chat":
        parsed = {**parsed, **{k: v for k, v in heuristic.items() if v not in {"", 0, None}}}
        intent = heuristic["intent"]
    return {"intent": intent, "action_args": parsed}


def heuristic_route(message: str, vision_summary: str | None) -> dict[str, Any]:
    text = message.lower()
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
    elif (
        any(word in message for word in ["查看", "列出", "显示", "待办", "哪些", "还有"])
        or is_pending_query
        or is_done_query
    ) and "搜索" not in message:
        payload["intent"] = "list"
        if is_done_query and "未完成" not in message:
            payload["status"] = "done"
        elif is_pending_query or "pending" in text:
            payload["status"] = "pending"
    elif any(word in message for word in ["搜索", "查找"]):
        payload["intent"] = "search"
        payload["query"] = message.replace("搜索", "").replace("查找", "").strip()
    elif any(word in message for word in ["完成", "搞定", "done"]) and "未完成" not in message:
        payload["intent"] = "done"
        payload["task_id"] = extract_first_int(message)
    elif any(word in message for word in ["删除", "移除"]):
        payload["intent"] = "delete"
        payload["task_id"] = extract_first_int(message)
    elif any(word in message for word in ["重新打开", "恢复"]):
        payload["intent"] = "reopen"
        payload["task_id"] = extract_first_int(message)
    elif any(word in message for word in ["修改", "更新"]):
        payload["intent"] = "update"
        payload["task_id"] = extract_first_int(message)
        payload["title_update"] = message
    return payload


def extract_first_int(message: str) -> int:
    digits = "".join(ch if ch.isdigit() else " " for ch in message).split()
    return int(digits[0]) if digits else 0


def extract_title_for_create(message: str, vision_summary: str | None) -> str:
    if vision_summary:
        return vision_summary
    cleaned = message
    prefixes = [
        "请添加一个待办：",
        "请添加一个待办:",
        "添加待办：",
        "添加待办:",
        "请添加待办：",
        "请添加待办:",
        "创建待办：",
        "创建待办:",
        "请创建待办：",
        "请创建待办:",
        "请记录：",
        "请记录:",
        "提醒我",
    ]
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    return cleaned or message


def execute_tool(state: AgentState) -> AgentState:
    intent = state["intent"]
    args = state.get("action_args", {})
    result: ToolResult

    if intent == "create":
        title = args.get("title") or state["normalized_message"]
        result = repo.create_task(title=title, created_at=args.get("created_at") or None)
    elif intent == "list":
        result = repo.list_tasks(status=args.get("status") or None)
    elif intent == "get":
        result = repo.get_task(task_id=int(args.get("task_id") or 0))
    elif intent == "update":
        result = repo.update_task(
            task_id=int(args.get("task_id") or 0),
            title=args.get("title_update") or None,
            created_at=args.get("created_at") or None,
        )
    elif intent == "delete":
        result = repo.delete_task(task_id=int(args.get("task_id") or 0))
    elif intent == "done":
        result = repo.done_task(
            task_id=int(args.get("task_id") or 0),
            completed_at=args.get("completed_at") or None,
        )
    elif intent == "reopen":
        result = repo.reopen_task(task_id=int(args.get("task_id") or 0))
    elif intent == "search":
        result = repo.search_tasks(query=args.get("query") or state["normalized_message"])
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


def write_response(state: AgentState) -> AgentState:
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
                system_prompt="你是一个中文 Todo 助手。请基于工具执行结果回复用户，语气直接，避免编造。如果工具结果已经足够清楚，可以原样简化复述。",
                user_prompt=context,
                temperature=0.2,
                max_tokens=300,
            ).strip()
            if polished:
                reply = polished
    if not reply:
        reply = tool_result.get("message") or "这次请求已处理，但模型没有生成额外说明。"

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
    }

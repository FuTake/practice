from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.audit_logger import log_todo_metric
from app.database import db
from app.time_utils import normalize_db_time, now_str, parse_db_datetime, parse_relative_time


def init_db() -> None:
    db.init()


def format_duration(start_str: str | None, end_str: str | None) -> str:
    if not start_str or not end_str:
        return ""
    start = parse_db_datetime(start_str)
    end = parse_db_datetime(end_str)
    if not start or not end:
        return ""
    diff = end - start
    total_minutes = int(diff.total_seconds() // 60)
    hours, minutes = divmod(max(total_minutes, 0), 60)
    return f"{hours}小时{minutes}分钟"


@dataclass(slots=True)
class ToolResult:
    ok: bool
    action: str
    message: str
    payload: dict[str, Any] | None = None


class TodoRepository:
    def create_task(self, title: str, created_at: str | None = None) -> ToolResult:
        start_time = parse_relative_time(created_at) or normalize_db_time(created_at) or now_str()
        new_id, affected = db.execute_write(
            "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
            (title, start_time),
        )
        log_todo_metric("create", "write_count", affected, f"task_id={new_id}")
        return ToolResult(
            ok=True,
            action="create",
            message=f"已创建任务 #{new_id}：{title}，开始时间 {start_time}",
            payload={"id": new_id, "title": title, "created_at": start_time},
        )

    def list_tasks(self, status: str | None = None) -> ToolResult:
        query = "SELECT id, title, status, created_at, completed_at, duration FROM tasks"
        params: tuple[Any, ...] = ()
        if status in {"pending", "done"}:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY id DESC"
        rows = [dict(row) for row in db.fetch_all(query, params)]
        log_todo_metric("list", "query_count", len(rows), f"status={status or 'all'}")
        if not rows:
            return ToolResult(True, "list", "## 任务列表\n\n当前没有符合条件的任务。", {"tasks": []})
        summary = "全部任务"
        if status == "pending":
            summary = "未完成任务"
        elif status == "done":
            summary = "已完成任务"
        return ToolResult(True, "list", render_task_list_markdown(summary, rows), {"tasks": rows})

    def get_task(self, task_id: int) -> ToolResult:
        row = db.fetch_one(
            "SELECT id, title, status, created_at, completed_at, duration FROM tasks WHERE id = ?",
            (task_id,),
        )
        log_todo_metric("get", "query_count", 1 if row else 0, f"task_id={task_id}")
        if not row:
            return ToolResult(False, "get", f"未找到任务 #{task_id}")
        item = dict(row)
        return ToolResult(
            True,
            "get",
            "\n".join(
                [
                    f"## 任务 #{item['id']}",
                    "",
                    f"- 标题：{item['title']}",
                    f"- 状态：{item['status']}",
                    f"- 开始时间：{item['created_at']}",
                    f"- 完成时间：{item['completed_at'] or '未完成'}",
                    f"- 耗时：{item['duration'] or '未完成'}",
                ]
            ),
            {"task": item},
        )

    def update_task(
        self, task_id: int, title: str | None = None, created_at: str | None = None
    ) -> ToolResult:
        row = db.fetch_one("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not row:
            return ToolResult(False, "update", f"未找到任务 #{task_id}")
        fields: list[str] = []
        params: list[Any] = []
        if title:
            fields.append("title = ?")
            params.append(title)
        if created_at:
            fields.append("created_at = ?")
            params.append(parse_relative_time(created_at) or normalize_db_time(created_at) or created_at)
        if not fields:
            return ToolResult(False, "update", "没有可更新的字段。")
        params.append(task_id)
        _, affected = db.execute_write(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", tuple(params))
        log_todo_metric("update", "write_count", affected, f"task_id={task_id}")
        return ToolResult(True, "update", f"已更新任务 #{task_id}")

    def delete_task(self, task_id: int) -> ToolResult:
        row = db.fetch_one("SELECT id FROM tasks WHERE id = ?", (task_id,))
        log_todo_metric("delete_check", "query_count", 1 if row else 0, f"task_id={task_id}")
        if not row:
            return ToolResult(False, "delete", f"未找到任务 #{task_id}")
        _, affected = db.execute_write("DELETE FROM tasks WHERE id = ?", (task_id,))
        log_todo_metric("delete", "write_count", affected, f"task_id={task_id}")
        return ToolResult(True, "delete", f"已删除任务 #{task_id}")

    def done_task(self, task_id: int, completed_at: str | None = None) -> ToolResult:
        row = db.fetch_one("SELECT created_at FROM tasks WHERE id = ?", (task_id,))
        log_todo_metric("done_check", "query_count", 1 if row else 0, f"task_id={task_id}")
        if not row:
            return ToolResult(False, "done", f"未找到任务 #{task_id}")
        end_time = parse_relative_time(completed_at) or normalize_db_time(completed_at) or now_str()
        duration = format_duration(row["created_at"], end_time)
        _, affected = db.execute_write(
            "UPDATE tasks SET status = 'done', completed_at = ?, duration = ? WHERE id = ?",
            (end_time, duration, task_id),
        )
        log_todo_metric("done", "write_count", affected, f"task_id={task_id}")
        return ToolResult(
            True,
            "done",
            f"已将任务 #{task_id} 标记为完成，耗时 {duration or '未知'}",
            {"id": task_id, "completed_at": end_time, "duration": duration},
        )

    def reopen_task(self, task_id: int) -> ToolResult:
        row = db.fetch_one("SELECT id FROM tasks WHERE id = ?", (task_id,))
        log_todo_metric("reopen_check", "query_count", 1 if row else 0, f"task_id={task_id}")
        if not row:
            return ToolResult(False, "reopen", f"未找到任务 #{task_id}")
        _, affected = db.execute_write(
            "UPDATE tasks SET status = 'pending', completed_at = NULL, duration = NULL WHERE id = ?",
            (task_id,),
        )
        log_todo_metric("reopen", "write_count", affected, f"task_id={task_id}")
        return ToolResult(True, "reopen", f"已重新打开任务 #{task_id}")

    def search_tasks(self, query: str) -> ToolResult:
        rows = [
            dict(row)
            for row in db.fetch_all(
                "SELECT id, title, status, created_at FROM tasks WHERE title LIKE ? ORDER BY id DESC",
                (f"%{query}%",),
            )
        ]
        log_todo_metric("search", "query_count", len(rows), f"query={query}")
        if not rows:
            return ToolResult(True, "search", f"## 搜索结果\n\n没有找到包含“{query}”的任务。", {"tasks": []})
        return ToolResult(
            True,
            "search",
            render_task_list_markdown(f"搜索结果：{query}", rows),
            {"tasks": rows},
        )

    def save_chat_log(
        self,
        title: str,
        user_message: str,
        assistant_message: str,
        intent: str | None,
        image_path: str | None,
    ) -> int:
        return db.execute(
            """
            INSERT INTO chat_logs (title, user_message, assistant_message, intent, image_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, user_message, assistant_message, intent, image_path, now_str()),
        )

    def list_chat_logs(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT id, title, user_message, assistant_message, intent, image_path, created_at
            FROM chat_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]


repo = TodoRepository()


def render_task_list_markdown(title: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"## {title}", ""]
    for row in rows:
        duration = row.get("duration") or "未完成"
        lines.extend(
            [
                f"### #{row['id']} {row['title']}",
                f"- 状态：`{row['status']}`",
                f"- 开始时间：{row['created_at']}",
                f"- 耗时：{duration}",
                "",
            ]
        )
    return "\n".join(lines).strip()

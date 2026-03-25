from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.audit_logger import log_todo_metric
from app.database import db
from app.time_utils import TIME_FMT, now_str, parse_relative_time


def init_db() -> None:
    db.init()


def format_duration(start_str: str | None, end_str: str | None) -> str:
    if not start_str or not end_str:
        return ""
    try:
        start = datetime.strptime(start_str, TIME_FMT)
        end = datetime.strptime(end_str, TIME_FMT)
    except ValueError:
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
        start_time = parse_relative_time(created_at) or created_at or now_str()
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
            return ToolResult(True, "list", "当前没有符合条件的任务。", {"tasks": []})
        lines = [
            f"#{row['id']} [{row['status']}] {row['title']}（开始：{row['created_at']}，耗时：{row['duration'] or '未完成'}）"
            for row in rows
        ]
        return ToolResult(True, "list", "\n".join(lines), {"tasks": rows})

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
            (
                f"任务 #{item['id']}：{item['title']}\n"
                f"状态：{item['status']}\n"
                f"开始：{item['created_at']}\n"
                f"完成：{item['completed_at'] or '未完成'}\n"
                f"耗时：{item['duration'] or '未完成'}"
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
            params.append(parse_relative_time(created_at) or created_at)
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
        end_time = parse_relative_time(completed_at) or completed_at or now_str()
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
            return ToolResult(True, "search", f"没有找到包含“{query}”的任务。", {"tasks": []})
        lines = [f"#{row['id']} [{row['status']}] {row['title']}（{row['created_at']}）" for row in rows]
        return ToolResult(True, "search", "\n".join(lines), {"tasks": rows})

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

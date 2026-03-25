from __future__ import annotations

from pathlib import Path

from app.time_utils import now_str


TODO_SCRIPT_DIR = Path(
    "/Users/zhishikaishi/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/todo/scripts"
)
TODO_PYTHON_LOG = TODO_SCRIPT_DIR / "python.log"


def log_todo_metric(operation: str, metric_type: str, count: int, detail: str = "") -> None:
    """把 todo 的查询和写入计数追加到旧 skill 的 python.log。"""
    TODO_SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    line = (
        f"[{now_str()}] operation={operation} metric={metric_type} "
        f"count={count}"
    )
    if detail:
        line += f" detail={detail}"
    print(line)
    with TODO_PYTHON_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{line}\n")

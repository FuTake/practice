#!/bin/zsh

set -euo pipefail

# 固定到项目目录，避免 launchd 从别的工作目录启动时找不到文件。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

# 直接调用虚拟环境里的 Python，并把进程名设置为 todoskill。
exec -a todoskill "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/main.py"

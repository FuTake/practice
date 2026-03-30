#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 兼容旧脚本名，实际复用 start_launchd.sh 的启动逻辑。
exec "$SCRIPT_DIR/start_launchd.sh"

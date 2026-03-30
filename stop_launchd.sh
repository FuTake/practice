#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SOURCE="$SCRIPT_DIR/launchd/com.zhishikaishi.todoskill.plist"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$AGENT_DIR/com.zhishikaishi.todoskill.plist"
LABEL="com.zhishikaishi.todoskill"
DOMAIN="gui/$(id -u)"

if [[ -f "$PLIST_DEST" ]]; then
  launchctl bootout "$DOMAIN" "$PLIST_DEST" 2>/dev/null || true
elif [[ -f "$PLIST_SOURCE" ]]; then
  # 如果用户还没复制到 LaunchAgents，也尝试按仓库内路径卸载一次。
  launchctl bootout "$DOMAIN" "$PLIST_SOURCE" 2>/dev/null || true
else
  echo "未找到可卸载的 plist 文件，按已停止处理: $LABEL"
  exit 0
fi

echo "已停止 launchd 服务: $LABEL"

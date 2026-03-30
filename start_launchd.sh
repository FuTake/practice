#!/bin/zsh

set -euo pipefail

# 基于脚本所在目录定位项目路径，避免从别的目录执行时找不到文件。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SOURCE="$SCRIPT_DIR/launchd/com.zhishikaishi.todoskill.plist"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$AGENT_DIR/com.zhishikaishi.todoskill.plist"
LABEL="com.zhishikaishi.todoskill"
DOMAIN="gui/$(id -u)"

if [[ ! -f "$PLIST_SOURCE" ]]; then
  echo "未找到 plist 文件: $PLIST_SOURCE" >&2
  exit 1
fi

mkdir -p "$AGENT_DIR"
cp "$PLIST_SOURCE" "$PLIST_DEST"

# 已加载时先卸载，再重新加载，保证配置更新生效。
launchctl bootout "$DOMAIN" "$PLIST_DEST" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST_DEST"
launchctl enable "$DOMAIN/$LABEL"
launchctl kickstart -k "$DOMAIN/$LABEL"

echo "已启动 launchd 服务: $LABEL"

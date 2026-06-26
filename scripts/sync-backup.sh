#!/usr/bin/env bash
# =============================================================================
# sync-backup.sh — 数据备份同步脚本
# 用于服务器端每天自动备份：仓库状态、Reasonix 配置、会话记录
# =============================================================================
set -euo pipefail

INSTALL_DIR="${1:-/opt/ai-system}"
BACKUP_DIR="${INSTALL_DIR}/backups/$(date +%Y%m%d)"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
GITHUB_USER="zhangjiayang6835-cyber"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 开始每日备份 ==="

mkdir -p "$BACKUP_DIR"

# 1. 仓库状态快照
echo "--- 仓库状态 ---"
for repo in eval-engine ai-training-gym honeycode-honeypot; do
    repo_path="$INSTALL_DIR/$repo"
    if [ -d "$repo_path/.git" ]; then
        cd "$repo_path"
        echo "=== $repo ===" > "$BACKUP_DIR/${repo}_status.txt"
        echo "Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')" >> "$BACKUP_DIR/${repo}_status.txt"
        echo "Last commit: $(git log -1 --format='%h %s (%ai)' 2>/dev/null || echo 'N/A')" >> "$BACKUP_DIR/${repo}_status.txt"
        echo "Uncommitted: $(git status --porcelain | wc -l) files" >> "$BACKUP_DIR/${repo}_status.txt"
        echo "  ✓ $repo"
    fi
done

# 2. Reasonix 配置备份
echo "--- 配置备份 ---"
if [ -d /root/.config/reasonix ]; then
    cp -r /root/.config/reasonix "$BACKUP_DIR/reasonix-config"
    echo "  ✓ Reasonix 配置已备份"
fi

# 3. 系统状态快照
echo "--- 系统状态 ---"
{
    echo "Date: $(date)"
    echo "Hostname: $(hostname)"
    echo "Uptime: $(uptime -p)"
    echo "---"
    echo "Disk:"
    df -h / 2>/dev/null | tail -1
    echo "---"
    echo "Memory:"
    free -h 2>/dev/null | grep Mem || true
    echo "---"
    echo "Docker:"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' 2>/dev/null || echo "Docker not running"
    echo "---"
    echo "Reasonix service:"
    systemctl status reasonix 2>/dev/null | grep -E '(Active|Loaded)' || echo "Not installed"
    echo "---"
    echo "Recent git sync:"
    tail -5 "$INSTALL_DIR/sync.log" 2>/dev/null || echo "No sync log"
} > "$BACKUP_DIR/system_status.txt"
echo "  ✓ 系统状态已记录"

# 4. 会话记录备份（如果有）
if [ -d /root/.reasonix/history ]; then
    mkdir -p "$BACKUP_DIR/reasonix-history"
    cp -r /root/.reasonix/history/*.jsonl "$BACKUP_DIR/reasonix-history/" 2>/dev/null || true
    echo "  ✓ 会话记录已备份"
fi

# 5. 打包压缩
echo "--- 打包压缩 ---"
ARCHIVE_NAME="backup-$(date +%Y%m%d_%H%M%S).tar.gz"
cd "$INSTALL_DIR/backups"
tar -czf "$ARCHIVE_NAME" "$(date +%Y%m%d)" 2>/dev/null
echo "  ✓ 备份包: backups/$ARCHIVE_NAME"

# 6. 清理过期备份
echo "--- 清理旧备份 ---"
find "$INSTALL_DIR/backups" -name "backup-*.tar.gz" -mtime "+$RETENTION_DAYS" -delete 2>/dev/null || true
find "$INSTALL_DIR/backups" -type d -name "20*" -mtime "+$RETENTION_DAYS" -exec rm -rf {} \; 2>/dev/null || true
echo "  ✓ 已清理 ${RETENTION_DAYS} 天前的备份"

echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 备份完成 ==="
echo "  备份路径: $BACKUP_DIR"
echo "  压缩包:   $INSTALL_DIR/backups/$ARCHIVE_NAME"
echo "  备份大小: $(du -sh "$INSTALL_DIR/backups/$ARCHIVE_NAME" 2>/dev/null | cut -f1)"

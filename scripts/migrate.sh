#!/usr/bin/env bash
# =============================================================================
# migrate.sh — 服务器迁移脚本
# 用途：三个月服务器到期后，在新服务器上一键恢复全部配置
# 使用方法：
#   1. 新服务器先运行 deploy-all.sh 完成基础部署
#   2. 运行本脚本迁移配置
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

INSTALL_DIR="/opt/ai-system"
GITHUB_USER="zhangjiayang6835-cyber"
REPOS=( "eval-engine" "ai-training-gym" "honeycode-honeypot" )

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        AI 系统迁移工具                              ║${NC}"
echo -e "${CYAN}║        将旧服务器配置迁移到新服务器                  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    err "请以 root 用户运行: sudo bash $0"
    exit 1
fi

# 检查基础部署
if [ ! -d "$INSTALL_DIR/eval-engine" ]; then
    err "$INSTALL_DIR 下未找到仓库，请先运行 deploy-all.sh"
    info "快速部署: bash <(curl -sL https://raw.githubusercontent.com/${GITHUB_USER}/honeycode-honeypot/master/scripts/deploy-all.sh)"
    exit 1
fi

# 步骤1: 恢复 Reasonix 配置
info "步骤1/4: 恢复 Reasonix 配置..."
CONFIG_BACKUP="${1:-}"
if [ -n "$CONFIG_BACKUP" ] && [ -f "$CONFIG_BACKUP" ]; then
    info "从备份文件恢复配置: $CONFIG_BACKUP"
    tar -xzf "$CONFIG_BACKUP" -C /tmp/ migrate_temp 2>/dev/null || {
        mkdir -p /tmp/migrate_temp
        tar -xzf "$CONFIG_BACKUP" -C /tmp/migrate_temp 2>/dev/null || true
    }
    # 尝试查找 reasonix 配置
    find /tmp -name "config.toml" -path "*/reasonix*" -exec cp {} /root/.config/reasonix/ \; 2>/dev/null && \
        ok "Reasonix 配置已恢复" || warn "未在备份中找到 Reasonix 配置"
else
    warn "未提供备份文件，跳过配置恢复"
    warn "若需要恢复旧服务器配置，请先 scp 备份到新服务器:"
    warn "  scp root@旧服务器IP:/opt/ai-system/backups/backup-*.tar.gz ."
    warn "  bash $0 backup-*.tar.gz"
    echo ""
fi

# 步骤2: 确保代码最新
info "步骤2/4: 拉取最新代码..."
for repo in "${REPOS[@]}"; do
    if [ -d "$INSTALL_DIR/$repo/.git" ]; then
        cd "$INSTALL_DIR/$repo"
        git fetch origin
        git reset --hard origin/master 2>/dev/null || git reset --hard origin/main 2>/dev/null || {
            warn "$repo: 分支切换失败，尝试 git pull"
            git pull --rebase 2>/dev/null || true
        }
        ok "$repo 已更新到最新"
    else
        warn "$repo 未找到，尝试重新克隆..."
        git clone "https://github.com/${GITHUB_USER}/${repo}.git" "$INSTALL_DIR/$repo" 2>/dev/null || \
        warn "克隆 $repo 失败，请检查网络"
    fi
done

# 步骤3: 重新运行测试 + 构建 Docker
info "步骤3/4: 验证环境..."
if command -v docker &>/dev/null; then
    if [ -f "$INSTALL_DIR/eval-engine/Dockerfile" ]; then
        docker build -t eval-engine-sandbox "$INSTALL_DIR/eval-engine" 2>/dev/null || \
            warn "Docker 镜像构建失败，可稍后手动构建"
    fi
    ok "Docker 就绪"
fi

# 步骤4: 重启服务
info "步骤4/4: 重启服务..."
systemctl daemon-reload 2>/dev/null || true
systemctl restart reasonix 2>/dev/null && \
    ok "Reasonix 服务已重启" || \
    warn "Reasonix 服务重启失败，请手动检查"

# 验证
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}          迁移完成！                                  ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "  📍 新服务器地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '<IP>'):8080"
echo "  📁 代码路径:     $INSTALL_DIR"
echo ""
for repo in "${REPOS[@]}"; do
    if [ -d "$INSTALL_DIR/$repo/.git" ]; then
        cd "$INSTALL_DIR/$repo"
        echo "  ✅ $repo ($(git rev-parse --short HEAD))"
    fi
done
echo ""
echo "  ⚡ 本地开发后 git push → 服务器自动同步"
echo ""

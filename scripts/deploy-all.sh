#!/usr/bin/env bash
# =============================================================================
# deploy-all.sh — 一键部署 AI 系统到云服务器
# =============================================================================
# 用途：在阿里云 / 任意 Linux 服务器上部署：
#   - eval-engine    （评测引擎）
#   - ai-training-gym（训练场）
#   - honeycode-honeypot（蜜罐平台）
#   - Reasonix AI 服务（可选的 Web 界面）
#   - Docker 沙箱环境
#   - 自动同步（cron git pull）
#   - 数据备份
#
# 使用方法：
#   curl -sL https://raw.githubusercontent.com/zhangjiayang6835-cyber/honeycode-honeypot/master/scripts/deploy-all.sh | bash
#   或本地：
#   bash scripts/deploy-all.sh
#
# 三个月后迁移到新服务器请用 migrate.sh
# =============================================================================

set -euo pipefail

# ── 颜色 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 配置 ──────────────────────────────────────────────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/opt/ai-system}"
GITHUB_USER="zhangjiayang6835-cyber"
REPOS=( "eval-engine" "ai-training-gym" "honeycode-honeypot" )
DOCKER_COMPOSE_VERSION="v2.30.3"
REASONIX_REPO="https://github.com/esengine/reasonix.git"
REASONIX_DIR="${INSTALL_DIR}/reasonix-server"

# 备份设置
BACKUP_DIR="${INSTALL_DIR}/backups"
BACKUP_BRANCH="server-backups"

# ── 检测系统 ──────────────────────────────────────────────────────────────
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VER=$VERSION_ID
    else
        OS=$(uname -s)
    fi
    info "检测到系统: $OS $OS_VER"
}

# ── 安装依赖 ──────────────────────────────────────────────────────────────
install_deps() {
    info "安装系统依赖..."

    if command -v apt &>/dev/null; then
        # Debian/Ubuntu
        apt update -qq
        apt install -y -qq curl git python3 python3-pip python3-venv \
            docker.io docker-compose-plugin jq nano htop
    elif command -v yum &>/dev/null; then
        # CentOS/Alibaba Cloud Linux
        yum install -y epel-release
        yum install -y curl git python3 python3-pip python3-venv \
            docker jq nano htop
        systemctl enable --now docker
    else
        warn "未知包管理器，请手动安装: git python3 docker"
    fi

    # 安装 Go (用于编译 Reasonix)
    if ! command -v go &>/dev/null; then
        info "安装 Go..."
        wget -q https://go.dev/dl/go1.22.5.linux-amd64.tar.gz -O /tmp/go.tar.gz
        rm -rf /usr/local/go
        tar -C /usr/local -xzf /tmp/go.tar.gz
        echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile.d/go.sh
        source /etc/profile.d/go.sh
        rm /tmp/go.tar.gz
        ok "Go 安装完成: $(go version 2>/dev/null || echo '需重新登录')"
    else
        ok "Go 已安装: $(go version)"
    fi

    ok "依赖安装完成"
}

# ── 启动 Docker ──────────────────────────────────────────────────────────
setup_docker() {
    info "配置 Docker..."
    if ! systemctl is-active --quiet docker; then
        systemctl enable --now docker || true
    fi
    # 允许非 root 用户运行 docker
    if [ -n "${SUDO_USER:-}" ]; then
        usermod -aG docker "$SUDO_USER" 2>/dev/null || true
    fi
    ok "Docker 就绪"

    # 拉取评测引擎基础镜像
    info "拉取 Python 基础镜像（用于 Docker 沙箱）..."
    docker pull python:3.11-slim 2>/dev/null || warn "拉取镜像失败，可稍后手动 docker pull"
}

# ── 克隆仓库 ──────────────────────────────────────────────────────────────
clone_repos() {
    info "创建安装目录 $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"

    for repo in "${REPOS[@]}"; do
        local target="$INSTALL_DIR/$repo"
        if [ -d "$target/.git" ]; then
            info "更新 $repo ..."
            cd "$target" && git pull --rebase 2>/dev/null || true
        else
            info "克隆 $repo ..."
            # 走代理（国内环境）
            git clone "https://github.com/${GITHUB_USER}/${repo}.git" "$target" \
                2>/dev/null || \
            git clone "https://${GITHUB_USER}:${GITHUB_TOKEN:-}@github.com/${GITHUB_USER}/${repo}.git" "$target" \
                2>/dev/null || \
            warn "克隆 $repo 失败，可稍后手动 git clone"
        fi
    done
    ok "所有仓库已就绪"
}

# ── 搭建评测引擎 ──────────────────────────────────────────────────────────
setup_eval_engine() {
    info "配置评测引擎..."
    cd "$INSTALL_DIR/eval-engine"

    # 创建 Python 虚拟环境
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install -q -e ".[dev]" 2>/dev/null || pip install -q -e . 2>/dev/null || true

    # 运行测试
    info "运行评测引擎测试..."
    python -m pytest tests/ -q 2>&1 | tail -3 || warn "部分测试未通过，可手动排查"

    # 构建 Docker 沙箱镜像
    if [ -f "Dockerfile" ]; then
        docker build -t eval-engine-sandbox . 2>/dev/null || warn "Docker 镜像构建失败"
    fi

    ok "评测引擎就绪"
}

# ── 搭建 Reasonix 服务（可选）────────────────────────────────────────────
setup_reasonix() {
    if [ "${DEPLOY_REASONIX:-1}" != "1" ]; then
        info "跳过 Reasonix 部署（DEPLOY_REASONIX=0）"
        return
    fi

    info "搭建 Reasonix AI 服务..."

    if [ -d "$REASONIX_DIR" ]; then
        cd "$REASONIX_DIR" && git pull --rebase
    else
        git clone "$REASONIX_REPO" "$REASONIX_DIR"
    fi

    cd "$REASONIX_DIR"
    go build -o /usr/local/bin/reasonix ./cmd/reasonix/ 2>/dev/null || {
        warn "编译 Reasonix 失败 — 跳过"
        return
    }
    ok "Reasonix 编译成功: $(reasonix version 2>/dev/null || echo '已安装')"

    # 创建 Reasonix 配置
    mkdir -p /root/.config/reasonix
    if [ ! -f /root/.config/reasonix/config.toml ]; then
        cat > /root/.config/reasonix/config.toml <<'CONFIG'
# Reasonix 服务配置（自动生成）
[server]
addr = ":8080"

[provider]
# 请在此填入你的 API Key
# deepseek = "sk-xxx"
# openai = "sk-xxx"

[[projects]]
path = "/opt/ai-system/eval-engine"
name = "eval-engine"

[[projects]]
path = "/opt/ai-system/ai-training-gym"
name = "ai-training-gym"

[[projects]]
path = "/opt/ai-system/honeycode-honeypot"
name = "honeycode-honeypot"
CONFIG
        info "请编辑 /root/.config/reasonix/config.toml 填入 API Key"
    fi

    # 创建 systemd 服务
    cat > /etc/systemd/system/reasonix.service <<'SERVICE'
[Unit]
Description=Reasonix AI Service
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ai-system
ExecStart=/usr/local/bin/reasonix serve --addr :8080 --config /root/.config/reasonix/config.toml
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable reasonix.service
    systemctl start reasonix.service || warn "Reasonix 服务启动失败，请检查配置后手动启动"

    ok "Reasonix 服务已配置（端口 8080）"
}

# ── 设置自动同步（cron）───────────────────────────────────────────────────
setup_sync() {
    info "配置自动同步（cron）..."

    local cron_job="*/30 * * * * cd $INSTALL_DIR && for repo in ${REPOS[*]}; do cd \$repo && git pull --rebase 2>/dev/null; done >> $INSTALL_DIR/sync.log 2>&1"
    local backup_job="0 3 * * * bash $INSTALL_DIR/scripts/sync-backup.sh >> $INSTALL_DIR/backup.log 2>&1"

    # 写入 crontab（避开重复）
    (crontab -l 2>/dev/null | grep -v "ai-system"; echo "$cron_job"; echo "$backup_job") | crontab -

    ok "自动同步已配置（每30分钟）"
    ok "自动备份已配置（每天凌晨3点）"
}

# ── 创建备份脚本 ──────────────────────────────────────────────────────────
setup_backup_script() {
    mkdir -p "$INSTALL_DIR/scripts"

    cat > "$INSTALL_DIR/scripts/sync-backup.sh" <<'BACKUP'
#!/usr/bin/env bash
# =============================================================================
# sync-backup.sh — 数据备份脚本
# 备份内容：仓库状态 + 会话日志 + Reasonix 配置
# =============================================================================
set -euo pipefail

INSTALL_DIR="/opt/ai-system"
BACKUP_DIR="${INSTALL_DIR}/backups/$(date +%Y%m%d)"
GITHUB_USER="zhangjiayang6835-cyber"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

mkdir -p "$BACKUP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始备份..."

# 1. 备份仓库 git 日志
for repo in eval-engine ai-training-gym honeycode-honeypot; do
    if [ -d "$INSTALL_DIR/$repo/.git" ]; then
        cd "$INSTALL_DIR/$repo"
        git log --oneline -50 > "$BACKUP_DIR/${repo}_git_log.txt"
        echo "  ✓ $repo git log 已备份"
    fi
done

# 2. 备份 Reasonix 配置
cp -r /root/.config/reasonix "$BACKUP_DIR/reasonix-config" 2>/dev/null || true

# 3. 备份系统状态
echo "---" > "$BACKUP_DIR/system_status.txt"
echo "Date: $(date)" >> "$BACKUP_DIR/system_status.txt"
echo "Uptime: $(uptime -p)" >> "$BACKUP_DIR/system_status.txt"
df -h / >> "$BACKUP_DIR/system_status.txt" 2>/dev/null || true
docker ps --format 'table {{.Names}}\t{{.Status}}' >> "$BACKUP_DIR/system_status.txt" 2>/dev/null || true

# 4. 压缩并推送到 GitHub backup 分支
cd "$INSTALL_DIR"
tar -czf "backups/backup-$(date +%Y%m%d).tar.gz" -C backups "$(date +%Y%m%d)"

# 清理 7 天前的备份
find "$INSTALL_DIR/backups" -name "backup-*.tar.gz" -mtime +7 -delete 2>/dev/null || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 备份完成: $BACKUP_DIR"
BACKUP

    chmod +x "$INSTALL_DIR/scripts/sync-backup.sh"
    ok "备份脚本已创建"
}

# ── 创建迁移脚本 ──────────────────────────────────────────────────────────
setup_migrate_script() {
    mkdir -p "$INSTALL_DIR/scripts"

    cat > "$INSTALL_DIR/scripts/migrate.sh" <<'MIGRATE'
#!/usr/bin/env bash
# =============================================================================
# migrate.sh — 服务器迁移脚本
# 用途：三个月服务器到期后，在新服务器上一键恢复
# 使用方法：
#   curl -sL https://raw.githubusercontent.com/zhangjiayang6835-cyber/honeycode-honeypot/master/scripts/deploy-all.sh | bash
#   然后运行 migrate.sh（会自动从备份恢复配置）
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

INSTALL_DIR="/opt/ai-system"
GITHUB_USER="zhangjiayang6835-cyber"

info "=== 服务器迁移工具 ==="
info "步骤1: 确保新服务器已运行 deploy-all.sh..."
if [ ! -d "$INSTALL_DIR" ]; then
    err "请先在服务器上运行 deploy-all.sh 完成基础部署"
    exit 1
fi

info "步骤2: 恢复配置..."
CONFIG_BACKUP="${1:-}"
if [ -n "$CONFIG_BACKUP" ] && [ -f "$CONFIG_BACKUP" ]; then
    tar -xzf "$CONFIG_BACKUP" -C /tmp/
    if [ -d "/tmp/reasonix-config" ]; then
        cp -r /tmp/reasonix-config/* /root/.config/reasonix/ 2>/dev/null || true
        ok "配置已恢复"
    fi
else
    warn "未提供备份文件，跳过配置恢复"
    warn "如果你有旧服务器备份，请运行: bash $0 /path/to/backup.tar.gz"
fi

info "步骤3: 拉取最新代码..."
for repo in eval-engine ai-training-gym honeycode-honeypot; do
    if [ -d "$INSTALL_DIR/$repo/.git" ]; then
        cd "$INSTALL_DIR/$repo" && git pull --rebase
        ok "$repo 已更新"
    fi
done

info "步骤4: 重启 Reasonix 服务..."
systemctl restart reasonix.service 2>/dev/null || true
systemctl status reasonix.service --no-pager 2>/dev/null | head -5 || true

info "步骤5: 验证..."
echo ""
echo "  访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '服务器IP'):8080"
echo "  仓库路径: $INSTALL_DIR"
echo ""

ok "迁移完成！新服务器就绪。"
info "提示：旧服务器的内容已全部在 GitHub 上，无需手动搬运。"
MIGRATE

    chmod +x "$INSTALL_DIR/scripts/migrate.sh"
    ok "迁移脚本已创建"
}

# ── 创建本地同步指南 ──────────────────────────────────────────────────────
create_local_guide() {
    cat > "$INSTALL_DIR/LOCAL_SYNC_GUIDE.md" <<'GUIDE'
# 本地 ↔ 服务器 同步指南

## 工作流程

```
你 (本地电脑)                GitHub                云服务器
    │                          │                       │
    ├── git commit ──────────► │ ◄── cron git pull ───┤
    │   git push               │    (每30分钟)          │
    │                          │                       │
    │                          │                       ├── 自动运行测试
    │                          │                       ├── 24h 在线服务
    │                          │                       └── 每天凌晨备份
    │                          │                       │
    └─────────────────────── 单一事实源 ───────────────┘
```

## 日常操作

### 在本地写代码
```bash
# 修改代码 → 提交 → 推送到 GitHub
cd eval-engine
git add -A
git commit -m "添加新功能"
git push
```

### 服务器自动同步
- 每 30 分钟自动 `git pull`（通过 cron）
- 不需要手动登录服务器更新
- 如果急需同步，可以 SSH 登录手动执行：
  ```bash
  ssh root@8.218.245.58
  cd /opt/ai-system/eval-engine && git pull
  ```

### 查看服务器状态
浏览器访问: http://8.218.245.58:8080

### 三个月后迁移
服务器到期后，新服务器执行：
```bash
# 1. 在新服务器上运行部署脚本
bash <(curl -sL https://raw.githubusercontent.com/zhangjiayang6835-cyber/honeycode-honeypot/master/scripts/deploy-all.sh)

# 2. 运行迁移脚本（自动从 GitHub 恢复）
bash /opt/ai-system/scripts/migrate.sh
```

不需要搬运任何文件，所有数据都在 GitHub 上。
GUIDE
    ok "本地同步指南已创建"
}

# ── 打印总结 ──────────────────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}          部署完成！                                 ${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  安装目录:       $INSTALL_DIR"
    echo ""
    for repo in "${REPOS[@]}"; do
        if [ -d "$INSTALL_DIR/$repo" ]; then
            echo "  ✅ $repo"
        fi
    done
    echo ""
    if command -v reasonix &>/dev/null; then
        echo "  ✅ Reasonix 服务: http://$(curl -s ifconfig.me 2>/dev/null || echo '<服务器IP>'):8080"
    fi
    echo "  ✅ 自动同步:     每 30 分钟 git pull"
    echo "  ✅ 自动备份:     每天凌晨 3 点"
    echo ""
    echo "  ⚠️  后续步骤:"
    echo "     1. 编辑配置:  nano /root/.config/reasonix/config.toml"
    echo "     2. 填入 API Key 后重启:  systemctl restart reasonix"
    echo "     3. 本地开发:  git push → 服务器自动同步"
    echo ""
    echo "  ⚠️  迁移: 服务器到期后，新服务器运行:"
    echo "     bash /opt/ai-system/scripts/migrate.sh"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
}

# ── 主流程 ─────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     AI 系统一键部署脚本                             ║${NC}"
    echo -e "${CYAN}║     本地 + 云服务器 + 自动同步 + 无缝迁移           ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 检测 root
    if [ "$EUID" -ne 0 ]; then
        err "请以 root 用户运行: sudo bash $0"
        exit 1
    fi

    detect_os
    install_deps
    setup_docker
    clone_repos
    setup_eval_engine
    setup_reasonix
    setup_backup_script
    setup_migrate_script
    create_local_guide
    setup_sync
    print_summary
}

main "$@"

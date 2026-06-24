#!/usr/bin/env bash
# =============================================================
# update_and_deploy.sh — 一键推送代码并部署到生产服务器
#
# 使用方式:
#   首次: bash setup_ssh.sh  (配置 SSH 免密，只需一次)
#   然后: bash update_and_deploy.sh
#
# 功能:
#   1. 清理 git 锁文件、还原 package-lock.json
#   2. 配置 git 凭证（macOS 钥匙串，首次输入 Token 后免输入）
#   3. 暂存并提交代码改动
#   4. 推送到 GitHub
#   5. SSH 到服务器备份 PostgreSQL
#   6. 服务器拉取代码、重建容器、执行迁移
# =============================================================
set -euo pipefail

# ── 配置 ───────────────────────────────────────────────────────
SSH_HOST="82.157.204.119"
SSH_USER="ubuntu"
APP_DIR="/opt/fee_sys"
GITHUB_USER="YX-NAS"
SSH_ALIAS="fee_sys_server"   # setup_ssh.sh 中配置的别名

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }
die()  { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }

# ── 1. 清理 git ────────────────────────────────────────────────
log "清理 git 环境..."
rm -f .git/index.lock 2>/dev/null || true

if ! git diff --quiet -- frontend/package-lock.json 2>/dev/null; then
    log "还原 package-lock.json..."
    git checkout -- frontend/package-lock.json 2>/dev/null || true
fi

# ── 2. 配置 git 凭证 ───────────────────────────────────────────
log "配置 git 凭证（macOS 钥匙串）..."
git config credential.helper osxkeychain
git config user.name "$GITHUB_USER"
git config user.email "nas@5176nas.online"

# ── 3. 暂存并提交 ──────────────────────────────────────────────
log "检查代码改动..."
git add -A

if git diff --cached --quiet; then
    warn "没有待提交的改动"
else
    log "提交代码..."
    git commit -m "feat: 告警系统优化 — severity 分级、AI 告警重试、统一告警中心

后端:
- 新增 severity 字段 (info/warning/critical)，迁移 006
- 修复 cost_spike 除零 bug
- cost_spike/no_usage 在用量同步时也评估
- AI 告警纳入重试基础设施
- 修复告警检查 N+1 查询
- 新建 AI 账号时 balance_low/sync_failed 默认启用
- 新增 /api/alerts/summary 和批量确认端点

前端:
- Alerts 页面统一费用+AI 告警
- Dashboard 新增告警摘要卡片
- 通知面板增加已读/未读筛选和自动刷新"
fi

# ── 4. 推送到 GitHub ───────────────────────────────────────────
log "推送到 GitHub..."
log "（首次推送会提示输入用户名和密码）"
log "（用户名: $GITHUB_USER  密码: 你的 GitHub Token）"
log "（存入钥匙串后后续不再提示）"

if git push origin main; then
    log "✅ 推送成功!"
else
    die "推送失败。请检查 GitHub Token 是否有效（需要 repo 权限）"
fi

# ── 5. 检查 SSH 配置 ───────────────────────────────────────────
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_ALIAS" "true" 2>/dev/null; then
    warn "SSH 免密未配置，将使用密码登录"
    warn "请先运行: bash setup_ssh.sh"
    warn "或直接输入密码继续..."
    SSH_TARGET="${SSH_USER}@${SSH_HOST}"
else
    SSH_TARGET="$SSH_ALIAS"
fi

# ── 6. 服务器部署 ──────────────────────────────────────────────
log "连接服务器部署..."

REMOTE_SCRIPT=$(cat <<'DEPLOY_EOF'
set -euo pipefail
cd /opt/fee_sys

echo "[服务器] === 1. 备份数据库 ==="
BACKUP_FILE="/opt/fee_sys/fee_sys_backup_$(date +%Y%m%d_%H%M%S).sql"
sudo docker compose exec -T postgres pg_dump -U fee_user fee_sys | sudo tee "$BACKUP_FILE" > /dev/null
echo "[服务器] 数据库已备份: $BACKUP_FILE"

echo "[服务器] === 2. 同步代码 (强制重置) ==="
sudo git fetch origin
sudo git clean -fd
sudo git reset --hard origin/main

echo "[服务器] === 3. 重建容器 ==="
sudo docker compose build

echo "[服务器] === 4. 启动容器 ==="
sudo docker compose up -d --remove-orphans

echo "[服务器] === 5. 等待数据库就绪 ==="
sleep 8

echo "[服务器] === 6. 执行数据库迁移 ==="
sudo docker compose exec -T api alembic upgrade head

echo "[服务器] === 7. 检查容器状态 ==="
sudo docker compose ps

echo "[服务器] ✅ 部署完成!"
DEPLOY_EOF
)

if ssh "$SSH_TARGET" "$REMOTE_SCRIPT"; then
    log "✅ 全部完成!"
    log "   代码已推送到 GitHub"
    log "   服务器已部署并执行迁移"
    log "   访问地址: https://fee.5176nas.online"
    log "   数据库备份在服务器: $APP_DIR/fee_sys_backup_*.sql"
else
    die "服务器部署失败，请检查 SSH 连接和服务器状态"
fi

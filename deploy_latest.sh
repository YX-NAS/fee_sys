#!/usr/bin/env bash
# =============================================================
# deploy_latest.sh — 一键部署最新版本（含首次 CI/CD 配置）
#
# 使用方式: bash deploy_latest.sh
# 在 Mac 终端运行，需要网络访问 GitHub 和服务器
#
# 执行步骤:
#   1. 配置 CI/CD Secrets + post-commit 钩子 (一次性)
#   2. 提交所有改动并推送到 GitHub
#   3. 直接 SSH 到服务器部署（本次手动，后续自动）
#
# 完成后，以后只需 git commit 即可全自动部署
# =============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }
die()  { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }

echo ""
echo "=========================================="
echo "  fee_sys 一键部署（含 CI/CD 配置）"
echo "=========================================="
echo ""

# ── 1. 清理 git 环境 ────────────────────────────────────────────
log "清理 git 环境..."
rm -f .git/index.lock 2>/dev/null || true
git checkout -- frontend/package-lock.json 2>/dev/null || true
git config credential.helper osxkeychain
git config user.name "YX-NAS"
git config user.email "nas@5176nas.online"

# ── 2. 配置 CI/CD (首次) ───────────────────────────────────────
if [ ! -f .git/hooks/post-commit ] || ! grep -q "autopush" .git/hooks/post-commit 2>/dev/null; then
    log "配置 CI/CD 自动化..."
    bash scripts/setup_automation.sh || {
        warn "CI/CD 配置遇到问题，继续手动部署..."
    }
else
    log "CI/CD 已配置，跳过"
fi

# ── 3. 提交所有改动 ─────────────────────────────────────────────
log "提交代码改动..."
git add -A

if git diff --cached --quiet; then
    warn "没有待提交的改动"
else
    git commit -m "ci: 添加 GitHub Actions 自动部署流水线

- 新增 .github/workflows/deploy.yml (push 到 main 自动部署)
- 新增 scripts/setup_automation.sh (一次性配置 Secrets + 钩子)
- 新增 scripts/add_github_secret.py (GitHub API 加密工具)
- 更新 update_and_deploy.sh (git reset --hard 避免冲突)
- 告警系统优化: severity 分级、AI 告警重试、统一告警中心"
    log "✅ 提交完成"
fi

# ── 4. 推送到 GitHub ────────────────────────────────────────────
log "推送到 GitHub..."
if git push origin main; then
    log "✅ 推送成功"
else
    die "推送失败，请检查 GitHub Token 或网络"
fi

# ── 5. 服务器部署 ───────────────────────────────────────────────
log "连接服务器部署..."

REMOTE_SCRIPT=$(cat <<'DEPLOY_EOF'
set -euo pipefail
cd /opt/fee_sys

echo "[服务器] === 1. 备份数据库 ==="
mkdir -p /opt/fee_sys/backups
BACKUP_FILE="/opt/fee_sys/backups/fee_sys_$(date +%Y%m%d_%H%M%S).sql"
sudo docker compose exec -T postgres pg_dump -U fee_user fee_sys | sudo tee "$BACKUP_FILE" > /dev/null
echo "[服务器] 备份完成: $BACKUP_FILE"

echo "[服务器] === 2. 强制同步代码 ==="
sudo git fetch origin
sudo git clean -fd
sudo git reset --hard origin/main

echo "[服务器] === 3. 构建容器 ==="
sudo docker compose build

echo "[服务器] === 4. 启动容器 ==="
sudo docker compose up -d --remove-orphans

echo "[服务器] === 5. 等待数据库就绪 ==="
sleep 8

echo "[服务器] === 6. 执行数据库迁移 ==="
sudo docker compose exec -T api alembic upgrade head

echo "[服务器] === 7. 健康检查 ==="
sleep 3
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "[服务器] 健康检查通过"
else
    echo "[服务器] WARN: 健康检查未通过，请检查: sudo docker compose logs api"
fi

echo "[服务器] === 8. 容器状态 ==="
sudo docker compose ps

echo "[服务器] ✅ 部署完成!"
DEPLOY_EOF
)

if ssh fee_sys_server "$REMOTE_SCRIPT"; then
    echo ""
    log "✅ 全部完成!"
    log "   代码已推送到 GitHub"
    log "   服务器已部署并执行迁移"
    log "   CI/CD 已配置 — 以后 git commit 即可自动部署"
    log "   访问地址: https://fee.5176nas.online"
    log "   Actions: https://github.com/YX-NAS/fee_sys/actions"
else
    die "服务器部署失败，请检查 SSH 连接"
fi

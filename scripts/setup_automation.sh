#!/usr/bin/env bash
# =============================================================
# setup_automation.sh — 一次性配置 CI/CD 自动化部署
#
# 使用方式: bash scripts/setup_automation.sh
#
# 功能:
#   1. 确认 SSH 免密登录（复用 setup_ssh.sh 的密钥）
#   2. 添加 GitHub Secrets (SERVER_HOST, SERVER_USER, SERVER_SSH_KEY)
#   3. 安装 git post-commit 钩子（提交后自动推送）
#
# 配置完成后:
#   - 你 commit 代码 → 钩子自动 push 到 GitHub
#   - GitHub 收到 push → Actions 自动 SSH 到服务器部署
#   - 全程无需手动干预
# =============================================================
set -euo pipefail

# ── 配置 ───────────────────────────────────────────────────────
SERVER_HOST="82.157.204.119"
SERVER_USER="ubuntu"
SSH_KEY_NAME="fee_sys_deploy"
GITHUB_OWNER="YX-NAS"
REPO_NAME="fee_sys"
SSH_ALIAS="fee_sys_server"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] $*${NC}"; }
info() { echo -e "${BLUE}[$(date '+%H:%M:%S')] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }
die()  { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }

echo ""
echo "=========================================="
echo "  fee_sys CI/CD 自动化配置"
echo "=========================================="
echo ""

# ── 1. 检查 SSH 密钥 ───────────────────────────────────────────
log "检查 SSH 密钥..."

if [ ! -f "$HOME/.ssh/${SSH_KEY_NAME}" ]; then
    warn "未找到 SSH 密钥 ~/.ssh/${SSH_KEY_NAME}"
    log "生成新的 SSH 密钥..."
    ssh-keygen -t ed25519 -f "$HOME/.ssh/${SSH_KEY_NAME}" -N "" -C "fee_sys_deploy"

    # 配置 SSH config
    if ! grep -q "$SSH_ALIAS" "$HOME/.ssh/config" 2>/dev/null; then
        cat >> "$HOME/.ssh/config" <<EOF
Host ${SSH_ALIAS}
    HostName ${SSH_HOST}
    User ${SERVER_USER}
    IdentityFile ~/.ssh/${SSH_KEY_NAME}
    StrictHostKeyChecking accept-new
EOF
        chmod 600 "$HOME/.ssh/config"
    fi

    log "复制公钥到服务器（请输入服务器密码）..."
    ssh-copy-id -i "$HOME/.ssh/${SSH_KEY_NAME}.pub" "${SERVER_USER}@${SERVER_HOST}"
else
    log "SSH 密钥已存在: ~/.ssh/${SSH_KEY_NAME}"
fi

# 测试 SSH 连接
log "测试 SSH 连接..."
if ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_ALIAS" "true" 2>/dev/null; then
    log "✅ SSH 免密登录正常"
else
    warn "SSH 免密登录失败，尝试复制公钥..."
    ssh-copy-id -i "$HOME/.ssh/${SSH_KEY_NAME}.pub" "${SERVER_USER}@${SERVER_HOST}" || \
        die "无法建立 SSH 连接，请先运行: bash setup_ssh.sh"
fi

# ── 2. 获取 GitHub Token ──────────────────────────────────────
log "获取 GitHub Token..."

# 尝试从 git credential helper 获取
GITHUB_TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill 2>/dev/null | grep '^password=' | cut -d= -f2- || true)

if [ -z "$GITHUB_TOKEN" ]; then
    echo ""
    echo "未找到已存储的 GitHub Token。"
    echo "请前往 https://github.com/settings/tokens 创建一个 Token (需要 repo 权限)"
    echo ""
    read -s -p "请粘贴你的 GitHub Token: " GITHUB_TOKEN
    echo ""
    [ -z "$GITHUB_TOKEN" ] && die "Token 不能为空"

    # 保存到 keychain
    printf "protocol=https\nhost=github.com\nusername=${GITHUB_OWNER}\npassword=${GITHUB_TOKEN}\n\n" | git credential approve 2>/dev/null || true
    log "Token 已保存到 macOS 钥匙串"
fi

# 验证 Token
log "验证 GitHub Token..."
USER_CHECK=$(curl -sf -H "Authorization: token ${GITHUB_TOKEN}" https://api.github.com/user 2>/dev/null | grep '"login"' | head -1 | cut -d'"' -f4 || true)
if [ -n "$USER_CHECK" ]; then
    log "✅ Token 有效 (用户: $USER_CHECK)"
else
    die "Token 验证失败，请检查 Token 是否有效"
fi

# ── 3. 添加 GitHub Secrets ────────────────────────────────────
log "添加 GitHub Actions Secrets..."

SCRIPT_DIR="$PROJECT_DIR/scripts"

python3 "$SCRIPT_DIR/add_github_secret.py" "$GITHUB_TOKEN" "$GITHUB_OWNER" "$REPO_NAME" "SERVER_HOST" "$SERVER_HOST"
python3 "$SCRIPT_DIR/add_github_secret.py" "$GITHUB_TOKEN" "$GITHUB_OWNER" "$REPO_NAME" "SERVER_USER" "$SERVER_USER"

# 读取私钥内容并添加为 secret
SSH_PRIVATE_KEY=$(cat "$HOME/.ssh/${SSH_KEY_NAME}")
python3 "$SCRIPT_DIR/add_github_secret.py" "$GITHUB_TOKEN" "$GITHUB_OWNER" "$REPO_NAME" "SERVER_SSH_KEY" "$SSH_PRIVATE_KEY"

log "✅ GitHub Secrets 配置完成"

# ── 4. 安装 git post-commit 钩子 ──────────────────────────────
log "配置 git post-commit 自动推送钩子..."

HOOK_FILE="$PROJECT_DIR/.git/hooks/post-commit"

# 检查是否已安装
if [ -f "$HOOK_FILE" ] && grep -q "autopush" "$HOOK_FILE" 2>/dev/null; then
    log "post-commit 钩子已存在，跳过"
else
    cat > "$HOOK_FILE" <<'HOOK'
#!/bin/bash
# =============================================================
# post-commit 钩子 — 自动推送到 GitHub (CI/CD 自动化)
# 提交后自动 push，触发 GitHub Actions 部署
# =============================================================
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

# 只在 main 分支自动推送
if [ "$BRANCH" != "main" ]; then
    exit 0
fi

# 跳过 rebase 期间
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
    exit 0
fi

# 推送
echo "[autopush] 推送到 origin/main..."
if git push origin main 2>&1 | sed 's/^/[autopush] /'; then
    echo "[autopush] ✅ 推送成功 — GitHub Actions 将自动部署"
else
    echo "[autopush] ⚠️ 推送失败，请手动运行: git push origin main"
fi
HOOK
    chmod +x "$HOOK_FILE"
    log "✅ post-commit 钩子已安装"
fi

# ── 5. 完成 ────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  ✅ CI/CD 自动化配置完成!"
echo "=========================================="
echo ""
echo "  工作流程:"
echo "    1. 你 commit 代码"
echo "    2. post-commit 钩子自动 push 到 GitHub"
echo "    3. GitHub Actions 自动 SSH 到服务器"
echo "    4. 服务器: 备份 → 拉代码 → 构建 → 迁移 → 健康检查"
echo ""
echo "  查看部署状态:"
echo "    https://github.com/${GITHUB_OWNER}/${REPO_NAME}/actions"
echo ""
echo "  手动触发部署 (可选):"
echo "    在 GitHub Actions 页面点击 'Run workflow'"
echo ""
echo "  查看服务器日志:"
echo "    ssh fee_sys_server 'cd /opt/fee_sys && sudo docker compose logs -f api'"
echo ""

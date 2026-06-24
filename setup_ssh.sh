#!/usr/bin/env bash
# =============================================================
# setup_ssh.sh — 一次性配置 SSH 免密登录（只需运行一次）
#
# 使用方式: bash setup_ssh.sh
# 功能: 生成 SSH 密钥并复制到服务器，之后 SSH 免密码
# =============================================================
set -euo pipefail

SSH_HOST="82.157.204.119"
SSH_USER="ubuntu"
KEY_NAME="fee_sys_deploy"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log() { echo -e "${GREEN}[$(date '+%H:%M:%S')] $*${NC}"; }

# 生成密钥（如果不存在）
if [ ! -f ~/.ssh/${KEY_NAME} ]; then
    log "生成 SSH 密钥..."
    ssh-keygen -t ed25519 -f ~/.ssh/${KEY_NAME} -N "" -C "fee_sys_deploy"
fi

# 配置 SSH config
log "配置 SSH config..."
mkdir -p ~/.ssh
SSH_CONFIG_ENTRY="Host fee_sys_server
    HostName ${SSH_HOST}
    User ${SSH_USER}
    IdentityFile ~/.ssh/${KEY_NAME}
    StrictHostKeyChecking accept-new"

if ! grep -q "fee_sys_server" ~/.ssh/config 2>/dev/null; then
    echo "$SSH_CONFIG_ENTRY" >> ~/.ssh/config
    chmod 600 ~/.ssh/config
fi

# 复制公钥到服务器（会提示输入密码，仅此一次）
log "复制公钥到服务器（会提示输入密码，仅此一次）..."
ssh-copy-id -i ~/.ssh/${KEY_NAME}.pub "${SSH_USER}@${SSH_HOST}"

# 测试免密登录
log "测试免密登录..."
if ssh -o BatchMode=yes fee_sys_server "echo 'SSH 免密登录配置成功!'"; then
    log "✅ SSH 配置完成，以后部署无需输入密码"
else
    echo -e "${YELLOW}[WARN] 免密登录测试失败，请检查密码是否正确${NC}"
fi

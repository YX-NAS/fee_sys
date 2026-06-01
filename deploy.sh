#!/usr/bin/env bash
# =============================================================
# deploy.sh — 一键部署费用管理系统到 Ubuntu 服务器
# 使用方式: bash deploy.sh
# 适用: Ubuntu 20.04/22.04/24.04, 域名 fee.5176nas.online
# =============================================================
set -euo pipefail

DOMAIN="fee.5176nas.online"
APP_DIR="/opt/fee_sys"
REPO="https://github.com/YX-NAS/fee_sys.git"
EMAIL="admin@${DOMAIN}"   # Let's Encrypt 通知邮箱，按需修改

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }
die()  { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }

# ── 1. 系统更新 & 安装依赖 ─────────────────────────────────────
log "更新系统包..."
apt-get update -qq
apt-get install -y -qq curl git nginx certbot python3-certbot-nginx ufw

# ── 2. 安装 Docker ─────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    log "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
else
    log "Docker 已安装: $(docker --version)"
fi

# ── 3. 安装 Docker Compose v2 ──────────────────────────────────
if ! docker compose version &>/dev/null 2>&1; then
    log "安装 Docker Compose v2..."
    COMPOSE_VER=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
    curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
else
    log "Docker Compose 已安装: $(docker compose version)"
fi

# ── 4. 拉取/更新代码 ───────────────────────────────────────────
if [ -d "${APP_DIR}/.git" ]; then
    log "更新代码..."
    git -C "${APP_DIR}" pull --ff-only
else
    log "克隆代码到 ${APP_DIR}..."
    git clone "${REPO}" "${APP_DIR}"
fi
cd "${APP_DIR}"

# ── 5. 创建 .env 文件（首次部署生成随机密钥）─────────────────
if [ ! -f .env ]; then
    log "生成 .env 配置文件..."
    PG_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    REDIS_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(20))")
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    # Fernet key — requires cryptography library (installed with the app)
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
        || python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
    cat > .env <<EOF
# Auto-generated on $(date)
POSTGRES_USER=fee_user
POSTGRES_PASSWORD=${PG_PASS}
POSTGRES_DB=fee_sys

REDIS_PASSWORD=${REDIS_PASS}

SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256

FIRST_ADMIN_USERNAME=admin
FIRST_ADMIN_EMAIL=admin@${DOMAIN}
FIRST_ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

ENCRYPTION_KEY=${FERNET_KEY}
EOF
    warn "已生成 .env 文件，请记录初始管理员密码："
    grep FIRST_ADMIN_PASSWORD .env
else
    log ".env 文件已存在，跳过生成"
fi

# ── 6. 防火墙配置 ─────────────────────────────────────────────
log "配置防火墙..."
ufw --force enable
ufw allow ssh
ufw allow 'Nginx Full'
ufw reload

# ── 7. 配置宿主机 nginx ────────────────────────────────────────
log "配置 nginx..."
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"
cp "${APP_DIR}/nginx/${DOMAIN}.conf" "${NGINX_CONF}"

# 首次仅用 HTTP（certbot 获取证书前 SSL 块会报错）
# 临时注释掉 HTTPS server 块
sed -i '/^server {/{n;/listen 443/,/^}/{ s/^/#TEMP# /}}' "${NGINX_CONF}" 2>/dev/null || true

ln -sf "${NGINX_CONF}" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 8. 获取 Let's Encrypt 证书 ────────────────────────────────
log "申请 SSL 证书..."
mkdir -p /var/www/certbot
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" \
    --redirect || warn "certbot 申请证书失败，请手动运行: certbot --nginx -d ${DOMAIN}"

# certbot 已自动修改 nginx 配置并启用 HTTPS，恢复完整配置
cp "${APP_DIR}/nginx/${DOMAIN}.conf" "${NGINX_CONF}"
nginx -t && systemctl reload nginx

# ── 9. 启动应用容器 ────────────────────────────────────────────
log "构建并启动 Docker 容器..."
docker compose pull --quiet 2>/dev/null || true
docker compose build
docker compose up -d --remove-orphans

# ── 10. 运行数据库迁移 ─────────────────────────────────────────
log "等待数据库就绪..."
sleep 8
docker compose exec api alembic upgrade head || warn "迁移失败，请手动运行: docker compose exec api alembic upgrade head"

# ── 完成 ───────────────────────────────────────────────────────
log "================================================="
log "✅ 部署完成!"
log "   访问地址: https://${DOMAIN}"
log "   查看日志: docker compose -f ${APP_DIR}/docker-compose.yml logs -f"
log "   管理员账号见 ${APP_DIR}/.env 中 FIRST_ADMIN_* 配置"
log "================================================="

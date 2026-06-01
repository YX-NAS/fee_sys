# 费用管理系统 (Fee Management System)

> 基于 FastAPI + Vue 3 构建的云资源费用管理平台，支持账号管理、费用流水追踪、余额预警、多渠道通知及费用分析。

**生产地址：** https://fee.5176nas.online  
**GitHub：** https://github.com/YX-NAS/fee_sys

---

## 功能特性

| 模块 | 功能 |
|------|------|
| 账号管理 | 云账号 CRUD、状态管理（启用/停用/归档）、标签分类 |
| 费用流水 | 充值 / 消费 / 调整 / 退款记录，余额快照 |
| 余额提醒 | 低余额阈值告警、充值周期提醒，冷却期防重复 |
| 通知渠道 | 站内通知 + 飞书机器人 + 企业微信 Webhook |
| 费用分析 | 趋势图、分类饼图、环比/同比对比、预算偏差 |
| 预算管理 | 按账号/月份设定预算，自动计算实际偏差 |
| 用户管理 | 管理员 / 运营 / 只读三级权限，JWT 认证 |

---

## 技术栈

**后端**
- Python 3.12 / FastAPI 0.111 / uvicorn（异步）
- SQLAlchemy 2.0 async + PostgreSQL 15
- Redis 7（缓存 + 会话）
- APScheduler（定时任务：余额巡检、提醒重试）
- Alembic（数据库迁移）
- python-jose（JWT）/ cryptography（Webhook URL 加密存储）

**前端**
- Vue 3.4 + Vite 5 + TypeScript
- Element Plus 2.7（UI 组件库）
- ECharts 5（图表）
- Pinia 2（状态管理）
- Axios（HTTP 客户端，含 Token 自动刷新）

**基础设施**
- Docker Compose（单机编排）
- nginx（宿主机反向代理 + HTTPS）
- Let's Encrypt（SSL 证书，certbot 自动续签）

---

## 目录结构

```
fee_sys/
├── backend/
│   ├── app/
│   │   ├── main.py          # 应用入口，lifespan 管理
│   │   ├── models.py        # 全部 ORM 模型（7 张表）
│   │   ├── schemas.py       # Pydantic v2 请求/响应模型
│   │   ├── security.py      # JWT、密码哈希、Fernet 加密
│   │   ├── dependencies.py  # FastAPI 依赖注入（认证守卫）
│   │   ├── routers/         # API 路由（8 个模块）
│   │   └── services/        # 业务逻辑（alerts/notifications/analytics/scheduler）
│   ├── alembic/             # 数据库迁移
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/           # 8 个页面组件
│   │   ├── components/      # Layout、NotificationPanel
│   │   ├── api/             # API 客户端（8 个模块）
│   │   ├── stores/          # Pinia（auth、notification）
│   │   ├── router/          # Vue Router（含权限守卫）
│   │   └── types/           # TypeScript 类型定义
│   ├── nginx.conf           # 容器内 nginx 配置
│   └── Dockerfile
├── nginx/
│   └── fee.5176nas.online.conf  # 宿主机 nginx 配置（含 HTTPS）
├── docker-compose.yml
├── deploy.sh                # 一键部署脚本
└── .env.example
```

---

## 快速开始

### 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/YX-NAS/fee_sys.git
cd fee_sys

# 2. 复制并编辑环境变量
cp .env.example .env
# 修改 .env 中的密码和密钥

# 3. 启动所有服务
docker compose up --build

# 4. 运行数据库迁移
docker compose exec api alembic upgrade head

# 5. 访问
#   前端: http://localhost:3000
#   API 文档: http://localhost:8000/docs
```

### 生产部署（服务器）

```bash
# 在服务器上一键部署（Ubuntu 20.04+）
curl -fsSL https://raw.githubusercontent.com/YX-NAS/fee_sys/main/deploy.sh | sudo bash
```

脚本自动完成：安装 Docker、nginx、certbot，申请 SSL 证书，启动容器，运行数据库迁移。

---

## 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `POSTGRES_PASSWORD` | 数据库密码 | 强随机字符串 |
| `REDIS_PASSWORD` | Redis 密码 | 强随机字符串 |
| `SECRET_KEY` | JWT 签名密钥（64字符） | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | Webhook URL 加密密钥（Fernet） | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `FIRST_ADMIN_USERNAME` | 首次启动自动创建的管理员账号 | `admin` |
| `FIRST_ADMIN_PASSWORD` | 首次启动自动创建的管理员密码 | 强随机字符串 |

---

## API 文档

启动后访问：
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

主要端点：

```
POST   /api/auth/login              # 登录
POST   /api/auth/refresh            # 刷新 Token
GET    /api/accounts                # 账号列表
POST   /api/transactions            # 添加流水
GET    /api/analytics/trend/{id}    # 消费趋势
GET    /api/analytics/comparison/{id}  # 环比/同比
GET    /api/notifications           # 站内通知
```

---

## 通知渠道配置

在「提醒规则」页面为账号配置告警规则时，支持：

**飞书机器人**：Webhook URL 格式 `https://open.feishu.cn/open-apis/bot/v2/hook/xxx`

**企业微信机器人**：Webhook URL 格式 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx`

> Webhook URL 在数据库中使用 Fernet 对称加密存储，密钥由 `ENCRYPTION_KEY` 环境变量控制。

---

## 数据库模型

```
User          # 系统用户（admin/operator/viewer）
Account       # 云账号（cloud/subscription/prepaid/other）
FeeTransaction # 费用流水（recharge/consume/adjustment/refund）
AlertConfig   # 提醒规则（balance_low/recharge_due）
AlertEvent    # 提醒事件记录
Notification  # 站内通知
Budget        # 月度预算
```

---

## License

MIT

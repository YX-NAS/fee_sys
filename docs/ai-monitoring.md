# AI 费用监控

## 能力与数据边界

- DeepSeek 请求通过 `/api/ai-gateway/v1` 转发，只保存模型、Token、费用、状态和耗时，不保存 Prompt 或回复正文。
- 火山引擎使用 AK/SK 同步方舟用量、费用账单和余额；账单金额优先，价格计算值用于核对。
- 厂商官网登录信息、官方 API 凭据和告警 Webhook 使用现有 Fernet 密钥加密。网关 Key 仅在创建时显示一次，数据库只保存 SHA-256 哈希。
- 流式连接没有收到最终 usage 时记为 `incomplete`，不会估算 Token。

## 管理员配置

1. 在“AI 费用监控 / 厂商账号”新增 DeepSeek 或火山引擎账号，保存厂商官网登录用户名和密码。登录信息仅用于账号归属和管理员维护，不用于模拟登录或网页抓取。
2. 在账号行点击“API 凭据”。DeepSeek 添加官方 API Key；火山引擎添加具备方舟用量、账单和余额权限的 AK/SK。一个账号可维护多套凭据并指定默认项。
3. 使用“测试”验证默认 API 凭据，再同步一次余额和历史费用。余额、用量和账单均通过厂商官方 API 获取。
4. DeepSeek 调用方在“网关 Key”创建 Key，并切换配置：

```text
Base URL: https://fee.5176nas.online/api/ai-gateway/v1
API Key: 系统创建的 fgw_ 开头 Gateway Key
```

厂商官方 API 凭据与 `fgw_` 网关 Key 是两类不同密钥：前者由系统访问厂商，后者由业务调用方访问本系统网关。列表接口不会返回两类密钥的明文。

5. 在“模型价格”维护价格有效期。历史版本不可修改，新价格必须新增版本且有效期不能重叠。
6. 新建账号时自动生成四类告警规则（余额不足、同步失败、费用突增、无用量数据），其中「余额不足」和「同步失败」默认启用并标记为 critical 级别；其余规则按需在「AI 费用监控 → 告警」标签页配置阈值后启用。

## 告警体系

每条告警规则带 `severity` 字段（`critical` / `warning` / `info`），按类型默认分级：

| 告警类型 | 默认级别 | 触发条件 | 评估时机 |
|---|---|---|---|
| `balance_low` | critical | 余额 < 阈值 | 余额同步成功后 |
| `sync_failed` | critical | 连续失败次数 ≥ 阈值 | 余额/用量同步失败后 |
| `cost_spike` | warning | 今日费用 > 近 7 日日均 × 倍数 | 余额同步 + 用量同步成功后 |
| `no_usage` | info | 昨日及今日均无用量数据 | 余额同步 + 用量同步成功后 |

`cost_spike` 在近 7 日总消费为 0 时不触发（无基线可比）。所有告警事件记录 per-channel 投递状态（站内 / webhook），失败的投递由定时任务每 30 分钟自动重试，最多 3 次。费用告警与 AI 告警共用同一套重试基础设施。

告警事件统一在「提醒中心 → 告警记录」查看，支持按来源（费用 / AI）、状态、严重级别、日期范围筛选，并可批量确认。Dashboard 顶部显示告警摘要卡片，按严重级别统计未处理告警并展示最近 5 条。

## 定时任务

| 时间 | 任务 |
|---|---|
| 每小时第 5 分钟 | 同步 DeepSeek 与火山引擎余额 |
| 每日 00:10 | 重建前一日 DeepSeek 网关汇总 |
| 每日 02:00 | 回补火山引擎最近三天用量和费用 |

## 部署与灰度

部署前必须备份 PostgreSQL，然后执行：

```bash
docker compose build api web
docker compose run --rm api alembic upgrade head
docker compose up -d
```

生产环境先设置 `AI_MONITOR_ADMIN_ONLY=true`。连续三天核对网关日汇总、DeepSeek 余额与火山账单后，改为 `false`；此时 operator 可查看并手工同步，viewer 只读。

## 回滚

应用回滚不会自动删除 AI 数据。若确认需要回退数据库，先停止 API，再恢复部署前的 PostgreSQL 备份；不要直接在生产执行 `alembic downgrade` 删除监控表。

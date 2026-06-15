# AI Token 费用监控规划

## 目标

- 按天采集多个 AI 厂商账号的 Token 用量、费用和可用余额。
- 支持按厂商、账号、模型、项目/业务标签查看趋势和成本构成。
- 支持余额不足、日费用突增、预算超限、同步失败告警。
- 复用现有用户权限、通知渠道、预算和定时任务能力。

## 非目标

- 第一阶段不做请求级 Prompt 内容采集。
- 第一阶段不替代厂商官方账单，仅作为运营监控和成本归集系统。
- 不假设所有厂商都提供相同的用量、费用或余额查询能力。

## 核心设计

### 1. AI 厂商账号

新增 `ai_provider_accounts`：

- `id`
- `provider`：厂商代码
- `name`：系统内账号名称
- `currency`
- `timezone`
- `credential_encrypted`：加密后的 API Key/访问凭据
- `provider_account_ref`：厂商侧账号、组织或项目标识
- `collection_mode`：`provider_api` / `gateway_log` / `manual`
- `status`
- `last_sync_at`
- `last_sync_status`
- `last_sync_error`
- `created_by_id`
- `created_at` / `updated_at`

凭据只允许写入和替换，不通过 API 返回明文。

### 2. 每日 Token 用量

新增 `ai_daily_usage`：

- `provider_account_id`
- `usage_date`
- `model`
- `project_ref`：项目、应用、API Key 或业务归属
- `input_tokens`
- `output_tokens`
- `cached_input_tokens`
- `reasoning_tokens`
- `request_count`
- `provider_reported_cost`
- `calculated_cost`
- `currency`
- `source`
- `raw_payload_hash`
- `synced_at`

唯一键建议：

`provider_account_id + usage_date + model + project_ref`

金额使用 `Numeric(18, 8)`，Token 使用 `BigInteger`。

### 3. 余额快照

新增 `ai_balance_snapshots`：

- `provider_account_id`
- `snapshot_time`
- `available_balance`
- `credit_granted`
- `credit_used`
- `currency`
- `source`

每天至少保留一条，必要时可按小时采集。

### 4. 模型价格

新增 `ai_model_prices`：

- `provider`
- `model`
- `effective_from` / `effective_to`
- 输入、输出、缓存、推理 Token 单价
- `currency`
- `unit_tokens`，默认每百万 Token

优先使用厂商返回费用；厂商只返回 Token 时，再按照有效期价格表计算。
历史价格不可原地覆盖，以保证历史费用可复算。

### 5. 同步任务

新增 Provider Adapter 接口：

- `test_connection()`
- `fetch_daily_usage(start_date, end_date)`
- `fetch_balance()`
- `capabilities()`：声明支持用量、费用、余额、模型维度等能力

同步流程：

1. 每日 01:30 同步前一天数据。
2. 同时回补最近 3 天，应对厂商账单延迟。
3. 使用 UPSERT 保证重复执行幂等。
4. 保存同步批次和错误信息。
5. 单账号失败不得阻塞其他账号。
6. 管理员可手动触发指定日期范围回补。

新增 `ai_sync_runs` 记录同步审计、耗时、范围和结果。

## 数据来源策略

按厂商能力选择：

1. `provider_api`：从厂商用量/账单接口采集。
2. `gateway_log`：系统统一代理 AI 请求，实时记录模型和 Token，再按日聚合。
3. `manual`：导入 CSV 或手工录入账单与余额。

厂商接口能力和字段在实施具体适配器前需要逐一验证。

## 费用与现有账本

- AI 每日明细保存在独立表中，避免普通 `fee_transactions` 膨胀。
- 每天按 AI 账号汇总后，可生成一条普通消费流水：
  - `category = ai_token`
  - `idempotency_key = ai:{account_id}:{date}`
- AI 厂商账号可关联现有 `Account`，从而复用预算、余额趋势和总费用分析。
- 余额以厂商快照为准，不通过消费流水倒推。

## 告警

扩展告警类型：

- `ai_balance_low`
- `ai_daily_cost_spike`
- `ai_daily_budget_exceeded`
- `ai_monthly_budget_threshold`
- `ai_sync_failed`
- `ai_no_usage_data`

建议规则：

- 余额低于固定金额。
- 当日费用超过近 7 天均值的指定倍数。
- 日费用超过日预算。
- 月累计达到预算的 80%、100%、120%。
- 连续两次同步失败。

继续复用站内通知、飞书和企业微信渠道。

## API

- `GET/POST /api/ai/accounts`
- `PUT/DELETE /api/ai/accounts/{id}`
- `POST /api/ai/accounts/{id}/test`
- `POST /api/ai/accounts/{id}/sync`
- `GET /api/ai/usage/daily`
- `GET /api/ai/usage/models`
- `GET /api/ai/balances`
- `GET /api/ai/overview`
- `GET /api/ai/sync-runs`
- `GET/POST/PUT /api/ai/prices`

账号凭据配置、价格维护、手工同步仅限管理员。

## 前端

新增一级菜单“AI 费用监控”，包含：

- 总览：今日/昨日费用、月累计、总 Token、剩余余额、异常账号。
- 厂商账号：连接状态、同步状态、余额、最后同步时间。
- 用量分析：按日趋势、厂商对比、模型排行、输入/输出 Token 构成。
- 预算告警：预算进度、异常增长和未处理告警。
- 同步记录：成功/失败批次、错误原因、手动重试。
- 模型价格：价格版本和生效时间管理。

## 权限与安全

- `admin`：账号凭据、价格、同步、预算和告警管理。
- `operator`：查看数据、手动同步、处理告警。
- `viewer`：只读。
- 凭据使用现有 Fernet 机制加密，日志中禁止输出密钥和完整厂商响应。
- 对厂商请求设置超时、重试、并发限制和脱敏错误日志。
- 不采集 Prompt、Completion 文本，默认只保存计量数据。

## 实施阶段

### 阶段 1：MVP

- 数据表和迁移。
- AI 账号管理与加密凭据。
- Provider Adapter 框架。
- 接入 1 个主力厂商。
- 每日用量、费用和余额同步。
- 总览、趋势、账号状态。
- 余额不足和同步失败告警。

### 阶段 2：多厂商与预算

- 增加其他厂商适配器。
- 模型价格版本管理。
- 日/月预算和费用突增告警。
- 汇总写入现有费用流水。
- CSV 导入和历史数据回补。

### 阶段 3：精细归集

- 接入统一 AI Gateway 或 SDK 埋点。
- 按项目、应用、团队、API Key 归集成本。
- 请求级元数据追踪，不保存提示词正文。
- 成本预测、额度耗尽日期预测和异常检测。

## 验证

- 单元测试：费用计算、价格生效区间、时区、幂等 UPSERT。
- 集成测试：适配器超时、限流、空数据、回补和部分失败。
- 权限测试：非管理员不能读取或修改凭据。
- 数据一致性：每日汇总金额与厂商账单抽样核对。
- 运行验证：定时同步、手动同步、告警通知和重试。

## 待确认

- 第一批需要接入的 AI 厂商及账号类型。
- 是否已有统一 AI Gateway 或可用的调用日志。
- 主计价币种及汇率处理方式。
- 成本需要归集到账号、项目、部门还是具体用户。
- 数据保存周期和是否需要请求级审计。

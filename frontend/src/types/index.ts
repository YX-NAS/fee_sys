// Shared TypeScript types matching backend schemas

export interface UserOut {
  id: string
  username: string
  email: string
  role: 'admin' | 'operator' | 'viewer'
  status: 'active' | 'inactive'
  created_at: string
  last_login_at: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserOut
}

export interface AccountOut {
  id: string
  name: string
  account_type: 'cloud' | 'subscription' | 'prepaid' | 'other'
  status: 'active' | 'inactive' | 'archived'
  description: string | null
  tags: string | null
  current_balance: string | null
  created_at: string
  updated_at: string
}

export interface TransactionOut {
  id: string
  account_id: string
  transaction_type: 'recharge' | 'consume' | 'adjustment' | 'refund'
  amount: string
  balance_after: string
  description: string | null
  category: string | null
  idempotency_key: string | null
  transaction_time: string
  created_at: string
}

export type AlertSeverity = 'info' | 'warning' | 'critical'
export type AlertEventStatus = 'pending' | 'sent' | 'failed' | 'acknowledged'

export interface AlertConfigOut {
  id: string
  account_id: string
  alert_type: 'balance_low' | 'recharge_due'
  severity: AlertSeverity
  threshold_amount: string | null
  recharge_cycle_days: number | null
  last_recharge_date: string | null
  cooldown_hours: number
  notify_inapp: boolean
  notify_webhook: boolean
  webhook_type: string | null
  is_enabled: boolean
  last_triggered_at: string | null
  created_at: string
}

export interface AlertEventOut {
  id: string
  config_id: string | null
  account_id: string
  alert_type: 'balance_low' | 'recharge_due'
  severity: AlertSeverity
  triggered_value: string | null
  threshold_value: string | null
  status: AlertEventStatus
  inapp_status: 'pending' | 'sent' | 'failed' | 'skipped'
  webhook_status: 'pending' | 'sent' | 'failed' | 'skipped'
  retry_count: number
  created_at: string
  acknowledged_at: string | null
}

export interface AIAlertRuleOut {
  id: string
  provider_account_id: string
  alert_type: 'balance_low' | 'sync_failed' | 'cost_spike' | 'no_usage'
  severity: AlertSeverity
  threshold_amount: string | null
  failure_count: number
  cooldown_hours: number
  notify_inapp: boolean
  notify_webhook: boolean
  webhook_type: string | null
  is_enabled: boolean
  last_triggered_at: string | null
}

export interface AIAlertEventOut {
  id: string
  provider_account_id: string
  alert_type: 'balance_low' | 'sync_failed' | 'cost_spike' | 'no_usage'
  severity: AlertSeverity
  triggered_value: string | null
  threshold_value: string | null
  message: string
  status: AlertEventStatus
  inapp_status: 'pending' | 'sent' | 'failed' | 'skipped'
  webhook_status: 'pending' | 'sent' | 'failed' | 'skipped'
  retry_count: number
  created_at: string
  acknowledged_at: string | null
}

export interface AlertSummary {
  total_unresolved: number
  by_severity: Record<string, number>
  recent: Array<{
    id: string
    source: 'fee' | 'ai'
    account_name: string
    alert_type: string
    severity: AlertSeverity
    status: AlertEventStatus
    message: string | null
    created_at: string
  }>
}

export interface NotificationOut {
  id: string
  alert_event_id: string | null
  title: string
  content: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface BudgetOut {
  id: string
  account_id: string
  year: number
  month: number
  budget_amount: string
  note: string | null
  created_at: string
}

export interface TrendPoint {
  period: string
  total_consume: string
  total_recharge: string
  net: string
}

export interface CategoryStat {
  category: string
  total: string
  count: number
  percentage: number
}

export interface ComparisonResult {
  current_period: string
  current_amount: string
  compare_period: string
  compare_amount: string
  change_amount: string
  change_rate: number | null
}

export interface BudgetVarianceResult {
  account_id: string
  year: number
  month: number
  budget_amount: string
  actual_amount: string
  variance: string
  variance_rate: number | null
}

export interface AnalyticsSummary {
  account_id: string
  current_balance: string
  this_month_consume: string
  this_month_recharge: string
  last_month_consume: string
  mom_change_rate: number | null
}

export interface PagedResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export type AIProvider = 'deepseek' | 'volcengine' | 'kimi' | 'alibaba' | 'huawei' | 'zhipu' | 'siliconflow'

export interface AIAccount {
  id: string
  provider: AIProvider
  name: string
  currency: string
  timezone: string
  provider_account_ref: string | null
  base_url: string | null
  status: 'active' | 'inactive' | 'error'
  portal_credentials_configured: boolean
  api_credentials_configured: boolean
  api_credentials_count: number
  last_sync_at: string | null
  last_sync_status: 'never' | 'running' | 'success' | 'failed'
  last_sync_error: string | null
  consecutive_failures: number
  created_at: string
  updated_at: string
}

export interface AIProviderAPICredential {
  id: string
  provider_account_id: string
  name: string
  credential_type: 'api_key' | 'ak_sk'
  key_hint: string | null
  is_active: boolean
  is_default: boolean
  last_tested_at: string | null
  last_test_status: 'success' | 'failed' | null
  last_test_error: string | null
  created_at: string
  updated_at: string
}

export interface AIOverview {
  today_cost: string
  yesterday_cost: string
  month_cost: string
  account_count: number
  abnormal_account_count: number
  balances: Array<{ account_id: string; balance: string; currency: string }>
}

export interface AIDailyUsage {
  id: string
  account_id: string
  date: string
  model: string
  input_tokens: number
  output_tokens: number
  cached_input_tokens: number
  reasoning_tokens: number
  request_count: number
  actual_cost: string | null
  calculated_cost: string
  cost_source: 'provider' | 'calculated'
  currency: string
}

export interface AIGatewayKey {
  id: string
  provider_account_id: string
  name: string
  key_prefix: string
  status: 'active' | 'disabled'
  rate_limit_per_minute: number
  expires_at: string | null
  last_used_at: string | null
  created_at: string
  key?: string
}

export interface AIPrice {
  id: string
  provider: AIProvider
  model: string
  input_price: string
  output_price: string
  cached_input_price: string
  reasoning_price: string
  unit_tokens: number
  currency: string
  effective_from: string
  effective_to: string | null
  created_at: string
}

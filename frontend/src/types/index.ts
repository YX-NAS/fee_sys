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

export interface AlertConfigOut {
  id: string
  account_id: string
  alert_type: 'balance_low' | 'recharge_due'
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
  triggered_value: string | null
  threshold_value: string | null
  status: 'pending' | 'sent' | 'failed' | 'acknowledged'
  inapp_status: 'pending' | 'sent' | 'failed' | 'skipped'
  webhook_status: 'pending' | 'sent' | 'failed' | 'skipped'
  retry_count: number
  created_at: string
  acknowledged_at: string | null
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

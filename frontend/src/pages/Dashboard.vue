<template>
  <div class="page">
    <h2 class="page-title">概览</h2>

    <!-- 告警摘要卡片 -->
    <el-card v-if="alertSummary" shadow="never" class="alert-summary-card" :class="{ 'has-critical': alertSummary.by_severity.critical > 0 }">
      <div class="alert-summary-head">
        <div class="alert-summary-title">
          <el-badge :value="alertSummary.total_unresolved || undefined" :max="99" type="danger">
            <span class="alert-icon">告警摘要</span>
          </el-badge>
        </div>
        <el-button link type="primary" @click="$router.push('/alerts')">查看全部</el-button>
      </div>
      <el-row :gutter="12" class="alert-stats">
        <el-col :span="8">
          <div class="alert-stat critical">
            <div class="alert-stat-num">{{ alertSummary.by_severity.critical || 0 }}</div>
            <div class="alert-stat-label">严重</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="alert-stat warning">
            <div class="alert-stat-num">{{ alertSummary.by_severity.warning || 0 }}</div>
            <div class="alert-stat-label">警告</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="alert-stat info">
            <div class="alert-stat-num">{{ alertSummary.by_severity.info || 0 }}</div>
            <div class="alert-stat-label">信息</div>
          </div>
        </el-col>
      </el-row>
      <div v-if="alertSummary.recent.length" class="alert-recent">
        <div v-for="r in alertSummary.recent.slice(0, 5)" :key="r.id" class="alert-recent-item" @click="$router.push('/alerts')">
          <el-tag :type="severityTagType(r.severity)" size="small" effect="dark">{{ severityLabel(r.severity) }}</el-tag>
          <el-tag size="small" :type="r.source === 'ai' ? 'primary' : 'info'">{{ r.source === 'ai' ? 'AI' : '费用' }}</el-tag>
          <span class="alert-recent-account">{{ r.account_name }}</span>
          <span class="alert-recent-msg">{{ r.message || alertTypeLabel(r.alert_type) }}</span>
          <span class="alert-recent-time">{{ dayjs(r.created_at).format('MM-DD HH:mm') }}</span>
        </div>
      </div>
      <div v-else class="alert-empty">暂无未处理告警</div>
    </el-card>

    <!-- 账号选择 -->
    <el-row :gutter="16" class="mb-16">
      <el-col :span="8">
        <el-select v-model="selectedAccountId" placeholder="选择账号查看详情" clearable style="width:100%" @change="onAccountChange">
          <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-col>
    </el-row>

    <!-- 汇总卡片 -->
    <el-row :gutter="16" class="mb-16" v-if="summary">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">当前余额</div>
          <div class="stat-value">¥{{ summary.current_balance }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">本月消费</div>
          <div class="stat-value consume">¥{{ summary.this_month_consume }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">本月充值</div>
          <div class="stat-value recharge">¥{{ summary.this_month_recharge }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">环比变化</div>
          <div class="stat-value" :class="momClass">
            {{ summary.mom_change_rate !== null ? (summary.mom_change_rate * 100).toFixed(1) + '%' : 'N/A' }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近流水 -->
    <el-card shadow="never" v-if="selectedAccountId">
      <template #header>最近流水（最新10条）</template>
      <el-table :data="recentTxns" size="small">
        <el-table-column prop="transaction_time" label="时间" width="160">
          <template #default="{ row }">{{ dayjs(row.transaction_time).format('YYYY-MM-DD HH:mm') }}</template>
        </el-table-column>
        <el-table-column prop="transaction_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="txnTagType(row.transaction_type)" size="small">{{ txnLabel(row.transaction_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="100">
          <template #default="{ row }">
            <span :class="row.transaction_type === 'consume' ? 'consume' : 'recharge'">
              {{ row.transaction_type === 'consume' ? '-' : '+' }}{{ row.amount }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="balance_after" label="余额" width="100" />
        <el-table-column prop="category" label="分类" />
        <el-table-column prop="description" label="说明" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import dayjs from 'dayjs'
import { accountApi } from '@/api/accounts'
import { transactionApi } from '@/api/transactions'
import { analyticsApi } from '@/api/analytics'
import { alertApi } from '@/api/alerts'
import type { AccountOut, AnalyticsSummary, TransactionOut, AlertSummary } from '@/types'

const accounts = ref<AccountOut[]>([])
const selectedAccountId = ref<string>('')
const summary = ref<AnalyticsSummary | null>(null)
const recentTxns = ref<TransactionOut[]>([])
const alertSummary = ref<AlertSummary | null>(null)

const momClass = computed(() => {
  if (!summary.value || summary.value.mom_change_rate === null) return ''
  return summary.value.mom_change_rate > 0 ? 'consume' : 'recharge'
})

async function onAccountChange(id: string) {
  if (!id) { summary.value = null; recentTxns.value = []; return }
  const [s, txns] = await Promise.all([
    analyticsApi.getSummary(id),
    transactionApi.list({ account_id: id, page: 1, page_size: 10 }),
  ])
  summary.value = s
  recentTxns.value = txns.items
}

function txnTagType(t: string) {
  return t === 'recharge' ? 'success' : t === 'consume' ? 'danger' : 'info'
}
function txnLabel(t: string) {
  return { recharge: '充值', consume: '消费', adjustment: '调整', refund: '退款' }[t] || t
}
function severityTagType(s: string) { return { critical: 'danger', warning: 'warning', info: 'info' }[s] || 'info' }
function severityLabel(s: string) { return { critical: '严重', warning: '警告', info: '信息' }[s] || s }
function alertTypeLabel(t: string) {
  const m: Record<string, string> = { balance_low: '余额不足', recharge_due: '充值周期', sync_failed: '同步失败', cost_spike: '费用突增', no_usage: '无用量数据' }
  return m[t] || t
}

let alertTimer: ReturnType<typeof setInterval> | null = null
onMounted(async () => {
  const res = await accountApi.list({ page: 1, page_size: 100, status: 'active' })
  accounts.value = res.items
  try { alertSummary.value = await alertApi.summary() } catch { /* ignore */ }
  alertTimer = setInterval(async () => { try { alertSummary.value = await alertApi.summary() } catch { /* ignore */ } }, 60000)
})
onBeforeUnmount(() => { if (alertTimer) clearInterval(alertTimer) })
</script>

<style scoped>
.page { padding: 20px; }
.page-title { margin: 0 0 16px; font-size: 20px; }
.mb-16 { margin-bottom: 16px; }
.stat-card { text-align: center; padding: 8px 0; }
.stat-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.stat-value { font-size: 24px; font-weight: bold; color: #303133; }
.consume { color: #f56c6c; }
.recharge { color: #67c23a; }
.alert-summary-card { margin-bottom: 16px; }
.alert-summary-card.has-critical { border-left: 3px solid #f56c6c; }
.alert-summary-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.alert-summary-title { font-size: 15px; font-weight: 600; }
.alert-icon { padding-right: 12px; }
.alert-stats { margin-bottom: 12px; }
.alert-stat { text-align: center; padding: 8px 0; border-radius: 4px; }
.alert-stat.critical { background: #fef0f0; }
.alert-stat.warning { background: #fdf6ec; }
.alert-stat.info { background: #f4f4f5; }
.alert-stat-num { font-size: 22px; font-weight: bold; }
.alert-stat.critical .alert-stat-num { color: #f56c6c; }
.alert-stat.warning .alert-stat-num { color: #e6a23c; }
.alert-stat.info .alert-stat-num { color: #909399; }
.alert-stat-label { font-size: 12px; color: #909399; }
.alert-recent-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid #f5f5f5; cursor: pointer; }
.alert-recent-item:hover { background: #f9f9f9; }
.alert-recent-account { font-size: 13px; color: #303133; white-space: nowrap; }
.alert-recent-msg { font-size: 12px; color: #606266; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.alert-recent-time { font-size: 12px; color: #c0c4cc; white-space: nowrap; }
.alert-empty { text-align: center; color: #909399; padding: 16px 0; }
</style>

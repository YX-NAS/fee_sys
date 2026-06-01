<template>
  <div class="page">
    <h2 class="page-title">概览</h2>

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
import { ref, computed, onMounted } from 'vue'
import dayjs from 'dayjs'
import { accountApi } from '@/api/accounts'
import { transactionApi } from '@/api/transactions'
import { analyticsApi } from '@/api/analytics'
import type { AccountOut, AnalyticsSummary, TransactionOut } from '@/types'

const accounts = ref<AccountOut[]>([])
const selectedAccountId = ref<string>('')
const summary = ref<AnalyticsSummary | null>(null)
const recentTxns = ref<TransactionOut[]>([])

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

onMounted(async () => {
  const res = await accountApi.list({ page: 1, page_size: 100, status: 'active' })
  accounts.value = res.items
})
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
</style>

<template>
  <div class="page">
    <h2 class="page-title">提醒中心</h2>
    <el-tabs v-model="activeTab">
      <!-- 提醒配置 -->
      <el-tab-pane label="提醒规则" name="configs">
        <el-button type="primary" style="margin-bottom:12px" @click="openConfigCreate">
          <el-icon><Plus /></el-icon>新增规则
        </el-button>
        <el-table :data="configs" v-loading="configLoading" border stripe @selection-change="onConfigSelection">
          <el-table-column label="账号" min-width="140">
            <template #default="{ row }">{{ accountName(row.account_id) }}</template>
          </el-table-column>
          <el-table-column prop="alert_type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="row.alert_type === 'balance_low' ? 'warning' : 'info'" size="small">
                {{ row.alert_type === 'balance_low' ? '余额不足' : '充值周期' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="级别" width="90">
            <template #default="{ row }">
              <el-tag :type="severityTagType(row.severity)" size="small" effect="dark">{{ severityLabel(row.severity) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="阈值/周期" width="120">
            <template #default="{ row }">
              {{ row.alert_type === 'balance_low' ? '¥' + row.threshold_amount : row.recharge_cycle_days + '天' }}
            </template>
          </el-table-column>
          <el-table-column prop="cooldown_hours" label="冷却(h)" width="90" />
          <el-table-column label="通知渠道" width="130">
            <template #default="{ row }">
              <el-tag v-if="row.notify_inapp" size="small" type="success">站内</el-tag>
              <el-tag v-if="row.notify_webhook" size="small" style="margin-left:4px">{{ row.webhook_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-switch v-model="row.is_enabled" @change="toggleConfig(row)" />
            </template>
          </el-table-column>
          <el-table-column label="上次触发" width="150">
            <template #default="{ row }">
              {{ row.last_triggered_at ? dayjs(row.last_triggered_at).format('MM-DD HH:mm') : '从未' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openConfigEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteConfig(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="configPage" :page-size="20" :total="configTotal"
          layout="total, prev, pager, next" class="pagination" @current-change="fetchConfigs" />
      </el-tab-pane>

      <!-- 提醒记录（统一：费用 + AI） -->
      <el-tab-pane :label="`告警记录${summary?.total_unresolved ? ' (' + summary.total_unresolved + ')' : ''}`" name="events">
        <el-row :gutter="12" style="margin-bottom:12px">
          <el-col :span="4">
            <el-select v-model="eventFilter.source" placeholder="来源" clearable @change="fetchEvents">
              <el-option label="费用告警" value="fee" />
              <el-option label="AI 告警" value="ai" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select v-model="eventFilter.status" placeholder="状态" clearable @change="fetchEvents">
              <el-option label="待发送" value="pending" />
              <el-option label="已发送" value="sent" />
              <el-option label="失败" value="failed" />
              <el-option label="已确认" value="acknowledged" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select v-model="eventFilter.severity" placeholder="级别" clearable @change="fetchEvents">
              <el-option label="严重" value="critical" />
              <el-option label="警告" value="warning" />
              <el-option label="信息" value="info" />
            </el-select>
          </el-col>
          <el-col :span="8">
            <el-date-picker v-model="eventFilter.dateRange" type="daterange" value-format="YYYY-MM-DDTHH:mm:ssZ"
              range-separator="至" start-placeholder="开始" end-placeholder="结束" style="width:100%" @change="fetchEvents" />
          </el-col>
          <el-col :span="4" style="text-align:right">
            <el-button :disabled="!selectedEvents.length" @click="batchAcknowledge">
              批量确认 ({{ selectedEvents.length }})
            </el-button>
            <el-button :icon="Refresh" circle @click="fetchEvents" style="margin-left:8px" />
          </el-col>
        </el-row>
        <el-table :data="events" v-loading="eventLoading" border stripe @selection-change="onEventSelection">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="created_at" label="时间" width="150">
            <template #default="{ row }">{{ dayjs(row.created_at).format('MM-DD HH:mm') }}</template>
          </el-table-column>
          <el-table-column label="来源" width="70">
            <template #default="{ row }">
              <el-tag :type="row._source === 'ai' ? 'primary' : 'info'" size="small">{{ row._source === 'ai' ? 'AI' : '费用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="级别" width="80">
            <template #default="{ row }">
              <el-tag :type="severityTagType(row.severity)" size="small" effect="dark">{{ severityLabel(row.severity) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="账号/内容" min-width="240">
            <template #default="{ row }">
              <div class="event-cell">
                <span class="event-account">{{ eventName(row) }}</span>
                <span v-if="row.message" class="event-msg">{{ row.message }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="触发值" width="90">
            <template #default="{ row }">
              {{ row.triggered_value !== null && row.triggered_value !== undefined ? '¥' + row.triggered_value : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="投递" width="110">
            <template #default="{ row }">
              <div class="channel-status">
                <el-tooltip :content="'站内: ' + row.inapp_status" placement="top">
                  <el-tag size="small" :type="channelTagType(row.inapp_status)">内</el-tag>
                </el-tooltip>
                <el-tooltip :content="'Webhook: ' + row.webhook_status" placement="top">
                  <el-tag size="small" :type="channelTagType(row.webhook_status)" style="margin-left:2px">钩</el-tag>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="retry_count" label="重试" width="50" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === 'failed'" size="small" type="warning" @click="retryEvent(row)">重试</el-button>
              <el-button v-if="row.status !== 'acknowledged'" size="small" @click="acknowledgeEvent(row)">确认</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="eventPage" :page-size="20" :total="eventTotal"
          layout="total, prev, pager, next" class="pagination" @current-change="fetchEvents" />
      </el-tab-pane>
    </el-tabs>

    <!-- 配置 dialog -->
    <el-dialog v-model="configDialog" :title="editConfig ? '编辑规则' : '新增规则'" width="480px">
      <el-form :model="cfgForm" :rules="cfgRules" ref="cfgFormRef" label-width="90px">
        <el-form-item label="账号" prop="account_id">
          <el-select v-model="cfgForm.account_id" style="width:100%" filterable>
            <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="提醒类型" prop="alert_type">
          <el-radio-group v-model="cfgForm.alert_type">
            <el-radio value="balance_low">余额不足</el-radio>
            <el-radio value="recharge_due">充值周期</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="严重级别">
          <el-select v-model="cfgForm.severity" style="width:100%">
            <el-option label="严重" value="critical" />
            <el-option label="警告" value="warning" />
            <el-option label="信息" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="cfgForm.alert_type === 'balance_low'" label="余额阈值" prop="threshold_amount">
          <el-input-number v-model="cfgForm.threshold_amount" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item v-if="cfgForm.alert_type === 'recharge_due'" label="周期(天)" prop="recharge_cycle_days">
          <el-input-number v-model="cfgForm.recharge_cycle_days" :min="1" style="width:100%" />
        </el-form-item>
        <el-form-item v-if="cfgForm.alert_type === 'recharge_due'" label="上次充值">
          <el-date-picker v-model="cfgForm.last_recharge_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" style="width:100%" />
        </el-form-item>
        <el-form-item label="冷却(小时)">
          <el-input-number v-model="cfgForm.cooldown_hours" :min="1" :max="720" style="width:100%" />
        </el-form-item>
        <el-form-item label="站内通知">
          <el-switch v-model="cfgForm.notify_inapp" />
        </el-form-item>
        <el-form-item label="Webhook">
          <el-switch v-model="cfgForm.notify_webhook" />
        </el-form-item>
        <template v-if="cfgForm.notify_webhook">
          <el-form-item label="类型">
            <el-select v-model="cfgForm.webhook_type" style="width:100%">
              <el-option label="飞书" value="feishu" />
              <el-option label="企业微信" value="wecom" />
            </el-select>
          </el-form-item>
          <el-form-item label="Webhook URL">
            <el-input v-model="cfgForm.webhook_url" placeholder="https://..." />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="configDialog = false">取消</el-button>
        <el-button type="primary" :loading="cfgSaving" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { FormInstance } from 'element-plus'
import { alertApi } from '@/api/alerts'
import { aiApi } from '@/api/ai'
import { accountApi } from '@/api/accounts'
import type { AlertConfigOut, AlertEventOut, AccountOut, AlertSummary } from '@/types'

const activeTab = ref('configs')
const accounts = ref<AccountOut[]>([])
const summary = ref<AlertSummary | null>(null)

// Config
const configs = ref<AlertConfigOut[]>([])
const configLoading = ref(false)
const configDialog = ref(false)
const cfgSaving = ref(false)
const editConfig = ref<AlertConfigOut | null>(null)
const cfgFormRef = ref<FormInstance>()
const configPage = ref(1)
const configTotal = ref(0)
const cfgForm = reactive<Record<string, unknown>>({
  account_id: '', alert_type: 'balance_low', severity: 'critical', threshold_amount: 100,
  recharge_cycle_days: 30, last_recharge_date: '', cooldown_hours: 24,
  notify_inapp: true, notify_webhook: false, webhook_type: 'feishu', webhook_url: '',
})
const cfgRules = {
  account_id: [{ required: true, message: '请选择账号' }],
  alert_type: [{ required: true }],
}

// Events (unified fee + AI)
const events = ref<(AlertEventOut & { _source: 'fee' | 'ai'; message?: string; provider_account_id?: string })[]>([])
const eventLoading = ref(false)
const eventTotal = ref(0)
const eventPage = ref(1)
const eventFilter = reactive<{ source: string; status: string; severity: string; dateRange: [string, string] | null }>({
  source: '', status: '', severity: '', dateRange: null,
})
const selectedEvents = ref<string[]>([])

let refreshTimer: ReturnType<typeof setInterval> | null = null

async function fetchConfigs() {
  configLoading.value = true
  try {
    const res = await alertApi.listConfigs({ page: configPage.value, page_size: 20 })
    configs.value = res.items
    configTotal.value = res.total
  } catch { ElMessage.error('加载规则失败') } finally { configLoading.value = false }
}

async function fetchEvents() {
  eventLoading.value = true
  try {
    const params: Record<string, unknown> = { page: eventPage.value, page_size: 20 }
    if (eventFilter.status) params.event_status = eventFilter.status
    if (eventFilter.severity) params.severity = eventFilter.severity
    if (eventFilter.dateRange) { params.start_time = eventFilter.dateRange[0]; params.end_time = eventFilter.dateRange[1] }

    const wantFee = !eventFilter.source || eventFilter.source === 'fee'
    const wantAI = !eventFilter.source || eventFilter.source === 'ai'

    const [feeRes, aiRes] = await Promise.all([
      wantFee ? alertApi.listEvents(params) : Promise.resolve({ items: [], total: 0 }),
      wantAI ? aiApi.alerts() : Promise.resolve({ rules: [], events: [] }),
    ])

    const feeItems = feeRes.items.map(e => ({ ...e, _source: 'fee' as const }))
    const aiItems = (aiRes.events as any[]).map(e => ({ ...e, _source: 'ai' as const }))
    let merged = [...feeItems, ...aiItems]
    // 客户端二次筛选（AI 告警不支持后端筛选）
    if (eventFilter.status) merged = merged.filter(e => e.status === eventFilter.status)
    if (eventFilter.severity) merged = merged.filter(e => e.severity === eventFilter.severity)
    if (eventFilter.dateRange) merged = merged.filter(e => {
      const t = dayjs(e.created_at)
      return t.isAfter(dayjs(eventFilter.dateRange![0])) && t.isBefore(dayjs(eventFilter.dateRange![1]))
    })
    merged.sort((a, b) => dayjs(b.created_at).valueOf() - dayjs(a.created_at).valueOf())
    eventTotal.value = merged.length
    const offset = (eventPage.value - 1) * 20
    events.value = merged.slice(offset, offset + 20)
  } catch { ElMessage.error('加载告警记录失败') } finally { eventLoading.value = false }
}

async function fetchSummary() {
  try { summary.value = await alertApi.summary() } catch { /* ignore */ }
}

function openConfigCreate() {
  editConfig.value = null
  Object.assign(cfgForm, { account_id: '', alert_type: 'balance_low', severity: 'critical', threshold_amount: 100, recharge_cycle_days: 30, last_recharge_date: '', cooldown_hours: 24, notify_inapp: true, notify_webhook: false, webhook_type: 'feishu', webhook_url: '' })
  configDialog.value = true
}
function openConfigEdit(row: AlertConfigOut) {
  editConfig.value = row
  Object.assign(cfgForm, { ...row, webhook_url: '' })
  configDialog.value = true
}

async function saveConfig() {
  await cfgFormRef.value?.validate()
  cfgSaving.value = true
  try {
    if (editConfig.value) {
      await alertApi.updateConfig(editConfig.value.id, cfgForm)
    } else {
      await alertApi.createConfig(cfgForm)
    }
    configDialog.value = false
    ElMessage.success('保存成功')
    await fetchConfigs()
  } finally { cfgSaving.value = false }
}

async function toggleConfig(row: AlertConfigOut) {
  await alertApi.updateConfig(row.id, { is_enabled: row.is_enabled })
}

async function deleteConfig(row: AlertConfigOut) {
  await ElMessageBox.confirm('确定删除该提醒规则吗？', '提示', { type: 'warning' })
  await alertApi.deleteConfig(row.id)
  ElMessage.success('已删除')
  await fetchConfigs()
}

async function acknowledgeEvent(row: any) {
  if (row._source === 'ai') {
    await aiApi.acknowledgeAlert(row.id)
  } else {
    await alertApi.acknowledgeEvent(row.id)
  }
  ElMessage.success('已确认')
  await Promise.all([fetchEvents(), fetchSummary()])
}

async function retryEvent(row: any) {
  if (row._source === 'ai') {
    ElMessage.info('AI 告警将在下次同步时自动重试')
  } else {
    await alertApi.retryEvent(row.id)
    ElMessage.success('已重试')
  }
  await fetchEvents()
}

function onEventSelection(rows: any[]) {
  selectedEvents.value = rows.map(r => r.id)
}

async function batchAcknowledge() {
  if (!selectedEvents.value.length) return
  // 费用告警走批量接口；AI 告警逐条确认
  const feeIds = events.value.filter(e => selectedEvents.value.includes(e.id) && e._source === 'fee').map(e => e.id)
  const aiIds = events.value.filter(e => selectedEvents.value.includes(e.id) && e._source === 'ai').map(e => e.id)
  if (feeIds.length) await alertApi.batchAcknowledge(feeIds)
  for (const id of aiIds) { await aiApi.acknowledgeAlert(id) }
  ElMessage.success(`已确认 ${selectedEvents.value.length} 条`)
  selectedEvents.value = []
  await Promise.all([fetchEvents(), fetchSummary()])
}
function onConfigSelection() { /* placeholder */ }

function accountName(id: string) {
  return accounts.value.find(a => a.id === id)?.name || id.slice(0, 8)
}
function eventName(row: any) {
  if (row._source === 'ai') {
    return aiAccountName(row.provider_account_id) + ' · ' + alertTypeLabel(row.alert_type)
  }
  return accountName(row.account_id) + ' · ' + (row.alert_type === 'balance_low' ? '余额不足' : '充值周期')
}
const aiAccounts = ref<any[]>([])
function aiAccountName(id: string) { return aiAccounts.value.find(a => a.id === id)?.name || id.slice(0, 8) }
function alertTypeLabel(t: string) {
  const m: Record<string, string> = { balance_low: '余额不足', sync_failed: '同步失败', cost_spike: '费用突增', no_usage: '无用量数据' }
  return m[t] || t
}

function severityTagType(s: string) { return { critical: 'danger', warning: 'warning', info: 'info' }[s] || 'info' }
function severityLabel(s: string) { return { critical: '严重', warning: '警告', info: '信息' }[s] || s }
function statusTagType(s: string) { return { pending: 'info', sent: 'success', failed: 'danger', acknowledged: '' }[s] || 'info' }
function statusLabel(s: string) { return { pending: '待发送', sent: '已发送', failed: '失败', acknowledged: '已确认' }[s] || s }
function channelTagType(s: string) {
  return { sent: 'success', failed: 'danger', pending: 'warning', skipped: 'info' }[s] || 'info'
}

onMounted(async () => {
  const [res, aiRes] = await Promise.all([
    accountApi.list({ page: 1, page_size: 100 }),
    aiApi.accounts().catch(() => []),
  ])
  accounts.value = res.items
  aiAccounts.value = aiRes
  await Promise.all([fetchConfigs(), fetchEvents(), fetchSummary()])
  refreshTimer = setInterval(() => { fetchSummary(); if (activeTab.value === 'events') fetchEvents() }, 60000)
})
onBeforeUnmount(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<style scoped>
.page { padding: 20px; }
.page-title { margin: 0 0 16px; font-size: 20px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
.event-cell { display: flex; flex-direction: column; gap: 2px; }
.event-account { font-size: 13px; color: #303133; }
.event-msg { font-size: 12px; color: #909399; }
.channel-status { display: flex; gap: 2px; }
</style>

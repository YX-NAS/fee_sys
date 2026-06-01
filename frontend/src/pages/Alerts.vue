<template>
  <div class="page">
    <h2 class="page-title">提醒中心</h2>
    <el-tabs v-model="activeTab">
      <!-- 提醒配置 -->
      <el-tab-pane label="提醒规则" name="configs">
        <el-button type="primary" style="margin-bottom:12px" @click="openConfigCreate">
          <el-icon><Plus /></el-icon>新增规则
        </el-button>
        <el-table :data="configs" v-loading="configLoading" border stripe>
          <el-table-column label="账号" width="140">
            <template #default="{ row }">{{ accountName(row.account_id) }}</template>
          </el-table-column>
          <el-table-column prop="alert_type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="row.alert_type === 'balance_low' ? 'warning' : 'info'" size="small">
                {{ row.alert_type === 'balance_low' ? '余额不足' : '充值周期' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="阈值/周期" width="120">
            <template #default="{ row }">
              {{ row.alert_type === 'balance_low' ? '¥' + row.threshold_amount : row.recharge_cycle_days + '天' }}
            </template>
          </el-table-column>
          <el-table-column prop="cooldown_hours" label="冷却(h)" width="90" />
          <el-table-column label="通知渠道" width="120">
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
      </el-tab-pane>

      <!-- 提醒事件 -->
      <el-tab-pane label="提醒记录" name="events">
        <el-row :gutter="12" style="margin-bottom:12px">
          <el-col :span="5">
            <el-select v-model="eventFilter.status" placeholder="状态" clearable @change="fetchEvents">
              <el-option label="待发送" value="pending" />
              <el-option label="已发送" value="sent" />
              <el-option label="失败" value="failed" />
              <el-option label="已确认" value="acknowledged" />
            </el-select>
          </el-col>
          <el-col :span="5">
            <el-select v-model="eventFilter.account_id" placeholder="账号" clearable @change="fetchEvents">
              <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
            </el-select>
          </el-col>
        </el-row>
        <el-table :data="events" v-loading="eventLoading" border stripe>
          <el-table-column prop="created_at" label="时间" width="150">
            <template #default="{ row }">{{ dayjs(row.created_at).format('MM-DD HH:mm') }}</template>
          </el-table-column>
          <el-table-column label="账号" width="120">
            <template #default="{ row }">{{ accountName(row.account_id) }}</template>
          </el-table-column>
          <el-table-column prop="alert_type" label="类型" width="100">
            <template #default="{ row }">{{ row.alert_type === 'balance_low' ? '余额不足' : '充值周期' }}</template>
          </el-table-column>
          <el-table-column label="触发值" width="100">
            <template #default="{ row }">
              {{ row.triggered_value !== null ? '¥' + row.triggered_value : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="retry_count" label="重试次数" width="80" />
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === 'failed'" size="small" type="warning" @click="retryEvent(row)">重试</el-button>
              <el-button v-if="row.status === 'sent'" size="small" @click="acknowledgeEvent(row)">确认</el-button>
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
          <el-select v-model="cfgForm.account_id" style="width:100%">
            <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="提醒类型" prop="alert_type">
          <el-radio-group v-model="cfgForm.alert_type">
            <el-radio value="balance_low">余额不足</el-radio>
            <el-radio value="recharge_due">充值周期</el-radio>
          </el-radio-group>
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
import { ref, reactive, onMounted } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { alertApi } from '@/api/alerts'
import { accountApi } from '@/api/accounts'
import type { AlertConfigOut, AlertEventOut, AccountOut } from '@/types'

const activeTab = ref('configs')
const accounts = ref<AccountOut[]>([])

// Config
const configs = ref<AlertConfigOut[]>([])
const configLoading = ref(false)
const configDialog = ref(false)
const cfgSaving = ref(false)
const editConfig = ref<AlertConfigOut | null>(null)
const cfgFormRef = ref<FormInstance>()
const cfgForm = reactive<Record<string, unknown>>({
  account_id: '', alert_type: 'balance_low', threshold_amount: 100,
  recharge_cycle_days: 30, last_recharge_date: '', cooldown_hours: 24,
  notify_inapp: true, notify_webhook: false, webhook_type: 'feishu', webhook_url: '',
})
const cfgRules = {
  account_id: [{ required: true, message: '请选择账号' }],
  alert_type: [{ required: true }],
}

// Events
const events = ref<AlertEventOut[]>([])
const eventLoading = ref(false)
const eventTotal = ref(0)
const eventPage = ref(1)
const eventFilter = reactive({ account_id: '', status: '' })

async function fetchConfigs() {
  configLoading.value = true
  const res = await alertApi.listConfigs({ page: 1, page_size: 100 })
  configs.value = res.items
  configLoading.value = false
}

async function fetchEvents() {
  eventLoading.value = true
  const params: Record<string, unknown> = { page: eventPage.value, page_size: 20 }
  if (eventFilter.account_id) params.account_id = eventFilter.account_id
  if (eventFilter.status) params.event_status = eventFilter.status
  const res = await alertApi.listEvents(params)
  events.value = res.items
  eventTotal.value = res.total
  eventLoading.value = false
}

function openConfigCreate() {
  editConfig.value = null
  Object.assign(cfgForm, { account_id: '', alert_type: 'balance_low', threshold_amount: 100, recharge_cycle_days: 30, last_recharge_date: '', cooldown_hours: 24, notify_inapp: true, notify_webhook: false, webhook_type: 'feishu', webhook_url: '' })
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
  } finally {
    cfgSaving.value = false
  }
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

async function acknowledgeEvent(row: AlertEventOut) {
  await alertApi.acknowledgeEvent(row.id)
  ElMessage.success('已确认')
  await fetchEvents()
}

async function retryEvent(row: AlertEventOut) {
  await alertApi.retryEvent(row.id)
  ElMessage.success('已重试')
  await fetchEvents()
}

function accountName(id: string) {
  return accounts.value.find(a => a.id === id)?.name || id.slice(0, 8)
}
function statusTagType(s: string) {
  return { pending: 'info', sent: 'success', failed: 'danger', acknowledged: '' }[s] || 'info'
}
function statusLabel(s: string) {
  return { pending: '待发送', sent: '已发送', failed: '失败', acknowledged: '已确认' }[s] || s
}

onMounted(async () => {
  const res = await accountApi.list({ page: 1, page_size: 100 })
  accounts.value = res.items
  await Promise.all([fetchConfigs(), fetchEvents()])
})
</script>

<style scoped>
.page { padding: 20px; }
.page-title { margin: 0 0 16px; font-size: 20px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
</style>

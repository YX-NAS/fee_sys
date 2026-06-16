<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <h2>AI 费用监控</h2>
        <p>火山引擎与 DeepSeek 用量、费用、余额和网关运行状态</p>
      </div>
      <el-button :icon="Refresh" circle title="刷新" @click="loadAll" />
    </div>

    <el-tabs v-model="activeTab" class="monitor-tabs">
      <el-tab-pane label="总览" name="overview">
        <el-row :gutter="12">
          <el-col v-for="card in summaryCards" :key="card.label" :xs="12" :sm="8" :lg="4">
            <el-card shadow="never" class="metric">
              <div class="metric-label">{{ card.label }}</div>
              <div class="metric-value">{{ card.value }}</div>
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="16" class="section">
          <el-col :xs="24" :lg="16">
            <el-card shadow="never">
              <template #header>近 14 天费用趋势</template>
              <div ref="chartEl" class="chart" />
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="8">
            <el-card shadow="never">
              <template #header>最新余额</template>
              <el-table :data="overview?.balances || []" height="320">
                <el-table-column label="账号">
                  <template #default="{ row }">{{ accountName(row.account_id) }}</template>
                </el-table-column>
                <el-table-column prop="balance" label="余额" align="right" />
                <el-table-column prop="currency" label="币种" width="70" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="厂商账号" name="accounts">
        <div class="toolbar">
          <el-button type="primary" :icon="Plus" @click="openAccount()">新增账号</el-button>
        </div>
        <el-table :data="accounts">
          <el-table-column prop="name" label="账号名称" min-width="150" />
          <el-table-column label="厂商" width="110">
            <template #default="{ row }">{{ providerName(row.provider) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : row.status === 'error' ? 'danger' : 'info'">{{ row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="凭据" width="170">
            <template #default="{ row }">
              <el-tag size="small" :type="row.portal_credentials_configured ? 'success' : 'warning'">官网登录</el-tag>
              <el-tag size="small" :type="row.api_credentials_configured ? 'success' : 'warning'" class="credential-tag">API {{ row.api_credentials_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_sync_at" label="最后同步" min-width="170">
            <template #default="{ row }">{{ formatTime(row.last_sync_at) }}</template>
          </el-table-column>
          <el-table-column prop="last_sync_error" label="同步信息" min-width="220" show-overflow-tooltip />
          <el-table-column label="操作" width="340" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="testConnection(row)">测试</el-button>
              <el-button link type="primary" @click="openApiCredentials(row)">API 凭据</el-button>
              <el-button link type="primary" @click="syncBalance(row)">余额</el-button>
              <el-button link type="primary" @click="syncUsage(row)">回补</el-button>
              <el-button link @click="openAccount(row)">编辑</el-button>
              <el-button link type="danger" @click="removeAccount(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="用量分析" name="usage">
        <div class="toolbar">
          <el-select v-model="usageAccount" clearable placeholder="全部账号" @change="loadUsage">
            <el-option v-for="item in accounts" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
          <el-date-picker v-model="usageRange" type="daterange" value-format="YYYY-MM-DD" @change="loadUsage" />
        </div>
        <el-table :data="usage">
          <el-table-column prop="date" label="日期" width="110" />
          <el-table-column label="账号" min-width="130"><template #default="{ row }">{{ accountName(row.account_id) }}</template></el-table-column>
          <el-table-column prop="model" label="模型" min-width="150" />
          <el-table-column prop="request_count" label="请求数" align="right" />
          <el-table-column prop="input_tokens" label="输入 Token" align="right" />
          <el-table-column prop="output_tokens" label="输出 Token" align="right" />
          <el-table-column prop="cached_input_tokens" label="缓存 Token" align="right" />
          <el-table-column label="费用" align="right">
            <template #default="{ row }">{{ row.actual_cost ?? row.calculated_cost }} {{ row.currency }}</template>
          </el-table-column>
          <el-table-column label="来源" width="90"><template #default="{ row }"><el-tag size="small">{{ row.cost_source === 'provider' ? '账单' : '计算' }}</el-tag></template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="网关 Key" name="keys">
        <div class="toolbar">
          <el-select v-model="keyAccount" placeholder="选择 DeepSeek 账号" @change="loadKeys">
            <el-option v-for="item in gatewayAccounts" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
          <el-button type="primary" :icon="Key" :disabled="!keyAccount" @click="keyDialog = true">创建 Key</el-button>
          <code class="base-url">Base URL: https://fee.5176nas.online/api/ai-gateway/v1</code>
        </div>
        <el-table :data="keys">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="key_prefix" label="Key 前缀" />
          <el-table-column prop="rate_limit_per_minute" label="每分钟限额" />
          <el-table-column prop="last_used_at" label="最后使用"><template #default="{ row }">{{ formatTime(row.last_used_at) }}</template></el-table-column>
          <el-table-column label="状态"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="{ row }"><el-button link type="danger" :disabled="row.status !== 'active'" @click="disableKey(row)">停用</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="告警" name="alerts">
        <el-table :data="alertRules">
          <el-table-column label="账号"><template #default="{ row }">{{ accountName(row.provider_account_id) }}</template></el-table-column>
          <el-table-column label="类型"><template #default="{ row }">{{ row.alert_type === 'balance_low' ? '余额不足' : '同步失败' }}</template></el-table-column>
          <el-table-column label="余额阈值" width="150"><template #default="{ row }">
            <el-input v-if="row.alert_type === 'balance_low'" v-model="row.threshold_amount" placeholder="阈值金额" />
            <span v-else>-</span>
          </template></el-table-column>
          <el-table-column label="失败次数" width="100"><template #default="{ row }">
            <el-input-number v-if="row.alert_type === 'sync_failed'" v-model="row.failure_count" :min="1" :max="20" size="small" controls-position="right" />
            <span v-else>-</span>
          </template></el-table-column>
          <el-table-column label="冷却(h)" width="90"><template #default="{ row }">
            <el-input-number v-model="row.cooldown_hours" :min="1" :max="720" size="small" controls-position="right" />
          </template></el-table-column>
          <el-table-column label="启用" width="70"><template #default="{ row }"><el-switch v-model="row.is_enabled" size="small" @change="saveAlert(row)" /></template></el-table-column>
          <el-table-column label="站内通知" width="100"><template #default="{ row }"><el-switch v-model="row.notify_inapp" size="small" @change="saveAlert(row)" /></template></el-table-column>
          <el-table-column label="操作" width="80"><template #default="{ row }">
            <el-button link type="primary" @click="saveAlert(row)">保存</el-button>
          </template></el-table-column>
        </el-table>
        <h3 class="subhead">最近告警</h3>
        <el-table :data="alertEvents">
          <el-table-column prop="created_at" label="时间"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
          <el-table-column prop="message" label="内容" min-width="360" />
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column label="操作" width="100"><template #default="{ row }"><el-button v-if="row.status === 'open'" link @click="ackAlert(row)">确认</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="同步记录" name="sync">
        <el-table :data="syncRuns">
          <el-table-column prop="started_at" label="开始时间"><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column>
          <el-table-column label="账号"><template #default="{ row }">{{ accountName(row.account_id) }}</template></el-table-column>
          <el-table-column prop="sync_type" label="类型" />
          <el-table-column prop="records_processed" label="记录数" />
          <el-table-column label="状态"><template #default="{ row }"><el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">{{ row.status }}</el-tag></template></el-table-column>
          <el-table-column prop="error" label="错误" min-width="300" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="模型价格" name="prices">
        <div class="toolbar"><el-button type="primary" :icon="Plus" @click="priceDialog = true">新增价格版本</el-button></div>
        <el-table :data="prices">
          <el-table-column label="厂商"><template #default="{ row }">{{ providerName(row.provider) }}</template></el-table-column>
          <el-table-column prop="model" label="模型" />
          <el-table-column prop="input_price" label="输入价" />
          <el-table-column prop="cached_input_price" label="缓存输入价" />
          <el-table-column prop="output_price" label="输出价" />
          <el-table-column prop="reasoning_price" label="推理价" />
          <el-table-column prop="effective_from" label="生效日期" />
          <el-table-column prop="effective_to" label="失效日期" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="accountDialog" :title="editingAccount ? '编辑厂商账号' : '新增厂商账号'" width="560px">
      <el-form :model="accountForm" label-width="110px">
        <el-form-item label="厂商"><el-select v-model="accountForm.provider" :disabled="!!editingAccount" placeholder="选择厂商">
          <el-option v-for="opt in providerOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select></el-form-item>
        <el-form-item label="账号名称"><el-input v-model="accountForm.name" /></el-form-item>
        <el-form-item label="官网用户名"><el-input v-model="accountForm.portal_username" placeholder="编辑时留空表示不更新" /></el-form-item>
        <el-form-item label="官网密码"><el-input v-model="accountForm.portal_password" type="password" show-password placeholder="编辑时留空表示不更新" /></el-form-item>
        <el-form-item v-if="accountForm.provider === 'volcengine'" label="账号标识"><el-input v-model="accountForm.provider_account_ref" /></el-form-item>
        <el-form-item label="API 地址"><el-input v-model="accountForm.base_url" :placeholder="accountForm.provider === 'deepseek' ? 'https://api.deepseek.com' : '可选'" /></el-form-item>
        <el-form-item label="币种"><el-input v-model="accountForm.currency" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="accountDialog = false">取消</el-button><el-button type="primary" @click="saveAccount">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="apiCredentialDialog" :title="`${credentialAccount?.name || ''} / 官方 API 凭据`" width="760px">
      <el-table :data="apiCredentials" empty-text="尚未配置 API 凭据">
        <el-table-column prop="name" label="名称" min-width="130" />
        <el-table-column prop="key_hint" label="凭据标识" min-width="120" />
        <el-table-column label="默认" width="70">
          <template #default="{ row }"><el-tag v-if="row.is_default" size="small" type="success">默认</el-tag></template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }"><el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="测试" width="90">
          <template #default="{ row }"><el-tag v-if="row.last_test_status" size="small" :type="row.last_test_status === 'success' ? 'success' : 'danger'">{{ row.last_test_status === 'success' ? '正常' : '失败' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="testApiCredential(row)">测试</el-button>
            <el-button v-if="!row.is_default" link @click="setDefaultApiCredential(row)">设为默认</el-button>
            <el-button link :type="row.is_active ? 'warning' : 'success'" @click="toggleApiCredential(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
            <el-button link type="danger" @click="removeApiCredential(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-divider content-position="left">新增凭据</el-divider>
      <el-form :model="apiCredentialForm" label-width="110px">
        <el-form-item label="凭据名称"><el-input v-model="apiCredentialForm.name" /></el-form-item>
        <template v-if="isApiKeyProvider(credentialAccount?.provider)">
          <el-form-item label="API Key"><el-input v-model="apiCredentialForm.api_key" type="password" show-password /></el-form-item>
        </template>
        <template v-else>
          <el-form-item label="Access Key"><el-input v-model="apiCredentialForm.access_key_id" /></el-form-item>
          <el-form-item label="Secret Key"><el-input v-model="apiCredentialForm.secret_access_key" type="password" show-password /></el-form-item>
          <el-form-item label="区域"><el-input v-model="apiCredentialForm.region" /></el-form-item>
        </template>
        <el-form-item label="设为默认"><el-switch v-model="apiCredentialForm.is_default" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="apiCredentialDialog = false">关闭</el-button><el-button type="primary" @click="createApiCredential">添加凭据</el-button></template>
    </el-dialog>

    <el-dialog v-model="keyDialog" title="创建网关 Key" width="480px">
      <el-form :model="keyForm" label-width="120px">
        <el-form-item label="名称"><el-input v-model="keyForm.name" /></el-form-item>
        <el-form-item label="每分钟请求数"><el-input-number v-model="keyForm.rate_limit_per_minute" :min="1" :max="10000" /></el-form-item>
        <el-form-item label="过期时间"><el-date-picker v-model="keyForm.expires_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="keyDialog = false">取消</el-button><el-button type="primary" @click="createKey">创建</el-button></template>
    </el-dialog>

    <el-dialog v-model="secretDialog" title="网关 Key 已创建" width="620px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" title="该 Key 仅显示一次，请立即配置到调用方。" />
      <el-input :model-value="createdSecret" readonly class="secret-input">
        <template #append><el-button :icon="CopyDocument" @click="copySecret" /></template>
      </el-input>
    </el-dialog>

    <el-dialog v-model="priceDialog" title="新增模型价格版本" width="620px">
      <el-form :model="priceForm" label-width="120px">
        <el-form-item label="厂商"><el-select v-model="priceForm.provider"><el-option label="DeepSeek" value="deepseek" /><el-option label="火山引擎" value="volcengine" /></el-select></el-form-item>
        <el-form-item label="模型"><el-input v-model="priceForm.model" /></el-form-item>
        <el-form-item label="输入价"><el-input-number v-model="priceForm.input_price" :precision="8" :min="0" /></el-form-item>
        <el-form-item label="缓存输入价"><el-input-number v-model="priceForm.cached_input_price" :precision="8" :min="0" /></el-form-item>
        <el-form-item label="输出价"><el-input-number v-model="priceForm.output_price" :precision="8" :min="0" /></el-form-item>
        <el-form-item label="推理价"><el-input-number v-model="priceForm.reasoning_price" :precision="8" :min="0" /></el-form-item>
        <el-form-item label="计价 Token"><el-input-number v-model="priceForm.unit_tokens" :min="1" /></el-form-item>
        <el-form-item label="生效日期"><el-date-picker v-model="priceForm.effective_from" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="priceDialog = false">取消</el-button><el-button type="primary" @click="createPrice">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { CopyDocument, Key, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { aiApi } from '@/api/ai'
import type {
  AIAccount, AIDailyUsage, AIGatewayKey, AIOverview, AIPrice,
  AIProvider, AIProviderAPICredential,
} from '@/types'

const loading = ref(false)
const activeTab = ref('overview')
const accounts = ref<AIAccount[]>([])
const overview = ref<AIOverview | null>(null)
const usage = ref<AIDailyUsage[]>([])
const prices = ref<AIPrice[]>([])
const keys = ref<AIGatewayKey[]>([])
const syncRuns = ref<any[]>([])
const alertRules = ref<any[]>([])
const alertEvents = ref<any[]>([])
const usageRange = ref<[string, string]>([dayjs().subtract(13, 'day').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')])
const usageAccount = ref('')
const keyAccount = ref('')
const chartEl = ref<HTMLElement>()
let chart: echarts.ECharts | null = null
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null

const accountDialog = ref(false)
const editingAccount = ref<AIAccount | null>(null)
const accountForm = ref<any>({})
const apiCredentialDialog = ref(false)
const credentialAccount = ref<AIAccount | null>(null)
const apiCredentials = ref<AIProviderAPICredential[]>([])
const apiCredentialForm = ref<any>({})
const keyDialog = ref(false)
const secretDialog = ref(false)
const createdSecret = ref('')
const keyForm = ref({ name: '', rate_limit_per_minute: 60, expires_at: null as string | null })
const priceDialog = ref(false)
const priceForm = ref<any>({})
const providerOptions = [{ label: 'DeepSeek', value: 'deepseek' }, { label: '火山引擎', value: 'volcengine' }, { label: 'Kimi', value: 'kimi' }, { label: '阿里云', value: 'alibaba' }, { label: '华为云', value: 'huawei' }, { label: '智谱', value: 'zhipu' }, { label: '硅基流动', value: 'siliconflow' }]
const gatewayAccounts = computed(() => accounts.value.filter(a => a.provider === "deepseek" || a.provider === "kimi" || a.provider === "siliconflow"))
const summaryCards = computed(() => [
  { label: '今日费用', value: `¥${overview.value?.today_cost || '0'}` },
  { label: '昨日费用', value: `¥${overview.value?.yesterday_cost || '0'}` },
  { label: '本月累计', value: `¥${overview.value?.month_cost || '0'}` },
  { label: '厂商账号', value: String(overview.value?.account_count || 0) },
  { label: '异常账号', value: String(overview.value?.abnormal_account_count || 0) },
])

function isApiKeyProvider(p?: string) { return p === "deepseek" || p === "kimi" || p === "zhipu" || p === "siliconflow" }
function providerName(provider: AIProvider) {
  const map: Record<string, string> = { deepseek: "DeepSeek", volcengine: "火山引擎", kimi: "Kimi", alibaba: "阿里云", huawei: "华为云", zhipu: "智谱", siliconflow: "硅基流动" }
  return map[provider] || provider }
function accountName(id: string) { return accounts.value.find(a => a.id === id)?.name || id.slice(0, 8) }
function formatTime(value: string | null) { return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-' }

async function loadAll() {
  loading.value = true
  try {
    accounts.value = await aiApi.accounts()
    overview.value = await aiApi.overview()
    if (!keyAccount.value && gatewayAccounts.value.length) keyAccount.value = gatewayAccounts.value[0].id
    await Promise.all([loadUsage(), loadPrices(), loadSyncRuns(), loadAlerts(), loadKeys()])
  } finally { loading.value = false }
}

async function loadUsage() {
  usage.value = await aiApi.dailyUsage({ start_date: usageRange.value[0], end_date: usageRange.value[1], account_id: usageAccount.value || undefined })
  await nextTick()
  if (!chart && chartEl.value) chart = echarts.init(chartEl.value)
  const byDate = new Map<string, number>()
  usage.value.forEach(row => byDate.set(row.date, (byDate.get(row.date) || 0) + Number(row.actual_cost ?? row.calculated_cost)))
  chart?.setOption({
    tooltip: { trigger: 'axis' }, grid: { left: 48, right: 24, top: 24, bottom: 36 },
    xAxis: { type: 'category', data: [...byDate.keys()] }, yAxis: { type: 'value', name: 'CNY' },
    series: [{ type: 'line', smooth: true, data: [...byDate.values()], itemStyle: { color: '#409eff' }, areaStyle: { opacity: 0.08 } }],
  })
}
async function loadPrices() { prices.value = await aiApi.prices() }
async function loadSyncRuns() { syncRuns.value = await aiApi.syncRuns() }
async function loadAlerts() { const data: any = await aiApi.alerts(); alertRules.value = data.rules; alertEvents.value = data.events }
async function loadKeys() { keys.value = keyAccount.value ? await aiApi.keys(keyAccount.value) : [] }

function openAccount(item?: AIAccount) {
  editingAccount.value = item || null
  accountForm.value = {
    provider: item?.provider || 'deepseek', name: item?.name || '',
    portal_username: '', portal_password: '',
    provider_account_ref: item?.provider_account_ref || '', base_url: item?.base_url || '',
    currency: item?.currency || 'CNY',
  }
  accountDialog.value = true
}

async function saveAccount() {
  const form = accountForm.value
  const payload: any = { name: form.name, currency: form.currency, base_url: form.base_url || null, provider_account_ref: form.provider_account_ref || null }
  if (form.portal_username) payload.portal_username = form.portal_username
  if (form.portal_password) payload.portal_password = form.portal_password
  if (editingAccount.value) await aiApi.updateAccount(editingAccount.value.id, payload)
  else {
    if (!form.portal_username || !form.portal_password) return ElMessage.warning('请填写厂商官网登录用户名和密码')
    payload.provider = form.provider
    await aiApi.createAccount(payload)
  }
  accountDialog.value = false
  ElMessage.success('账号已保存')
  await loadAll()
}

function defaultApiCredentialForm() {
  return { name: '', api_key: '', access_key_id: '', secret_access_key: '', region: 'cn-beijing', is_default: false }
}
async function openApiCredentials(item: AIAccount) {
  credentialAccount.value = item
  apiCredentialForm.value = defaultApiCredentialForm()
  apiCredentials.value = await aiApi.apiCredentials(item.id)
  apiCredentialDialog.value = true
}
async function reloadApiCredentials() {
  if (!credentialAccount.value) return
  apiCredentials.value = await aiApi.apiCredentials(credentialAccount.value.id)
}
async function createApiCredential() {
  const account = credentialAccount.value
  if (!account) return
  const form = apiCredentialForm.value
  const credentials = isApiKeyProvider(account.provider)
    ? { api_key: form.api_key }
    : { access_key_id: form.access_key_id, secret_access_key: form.secret_access_key, region: form.region }
  if (!form.name || Object.values(credentials).some(value => !value)) return ElMessage.warning('请完整填写 API 凭据')
  await aiApi.createApiCredential(account.id, {
    name: form.name,
    credential_type: isApiKeyProvider(account.provider) ? 'api_key' : 'ak_sk',
    credentials,
    is_default: form.is_default,
  })
  apiCredentialForm.value = defaultApiCredentialForm()
  ElMessage.success('API 凭据已添加')
  await Promise.all([reloadApiCredentials(), loadAll()])
}
async function testApiCredential(item: AIProviderAPICredential) {
  if (!credentialAccount.value) return
  await aiApi.testApiCredential(credentialAccount.value.id, item.id)
  ElMessage.success('API 凭据连接正常')
  await reloadApiCredentials()
}
async function setDefaultApiCredential(item: AIProviderAPICredential) {
  if (!credentialAccount.value) return
  await aiApi.updateApiCredential(credentialAccount.value.id, item.id, { is_default: true })
  await reloadApiCredentials()
}
async function toggleApiCredential(item: AIProviderAPICredential) {
  if (!credentialAccount.value) return
  await aiApi.updateApiCredential(credentialAccount.value.id, item.id, { is_active: !item.is_active })
  await Promise.all([reloadApiCredentials(), loadAll()])
}
async function removeApiCredential(item: AIProviderAPICredential) {
  if (!credentialAccount.value) return
  await ElMessageBox.confirm(`删除 API 凭据“${item.name}”？`, '删除确认', { type: 'warning' })
  await aiApi.deleteApiCredential(credentialAccount.value.id, item.id)
  await Promise.all([reloadApiCredentials(), loadAll()])
}

async function testConnection(item: AIAccount) { await aiApi.testAccount(item.id); ElMessage.success('连接正常') }
async function syncBalance(item: AIAccount) { await aiApi.syncBalance(item.id); ElMessage.success('余额已同步'); await loadAll() }
async function syncUsage(item: AIAccount) {
  const [start, end] = usageRange.value
  const result: any = await aiApi.syncAccount(item.id, { start_date: start, end_date: end })
  ElMessage[result.status === 'success' ? 'success' : 'warning'](`同步完成，处理 ${result.records_processed} 条`)
  await loadAll()
}
async function removeAccount(item: AIAccount) {
  await ElMessageBox.confirm(`删除账号“${item.name}”及其监控数据？`, '删除确认', { type: 'warning' })
  await aiApi.deleteAccount(item.id)
  await loadAll()
}
async function createKey() {
  const item = await aiApi.createKey(keyAccount.value, keyForm.value)
  createdSecret.value = item.key || ''
  keyDialog.value = false
  secretDialog.value = true
  keyForm.value = { name: '', rate_limit_per_minute: 60, expires_at: null }
  await loadKeys()
}
async function copySecret() { await navigator.clipboard.writeText(createdSecret.value); ElMessage.success('已复制') }
async function disableKey(item: AIGatewayKey) { await aiApi.disableKey(item.id); await loadKeys() }
async function saveAlert(row: any) { await aiApi.updateAlert(row.provider_account_id, row.alert_type, { ...row, webhook_url: null }); ElMessage.success('告警规则已更新') }
async function ackAlert(row: any) { await aiApi.acknowledgeAlert(row.id); await loadAlerts() }
async function createPrice() {
  await aiApi.createPrice({ ...priceForm.value, currency: 'CNY', effective_to: null })
  priceDialog.value = false
  priceForm.value = defaultPrice()
  await loadPrices()
}
async function refreshData() {
  const activeAccounts = accounts.value.filter(a => a.status !== 'inactive')
  await Promise.allSettled(activeAccounts.map(a => aiApi.syncBalance(a.id).catch(() => {})))
  await loadAll()
}

function defaultPrice() {
  return { provider: 'deepseek', model: '', input_price: 0, output_price: 0, cached_input_price: 0, reasoning_price: 0, unit_tokens: 1000000, effective_from: dayjs().format('YYYY-MM-DD') }
}

onMounted(() => {
  priceForm.value = defaultPrice()
  loadAll()
  autoRefreshTimer = setInterval(refreshData, 3600000)
})
onBeforeUnmount(() => {
  if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null }
  chart?.dispose()
})
</script>

<style scoped>
.page { padding: 20px; }
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.page-head h2 { margin: 0; font-size: 20px; }
.page-head p { margin: 5px 0 0; color: #909399; font-size: 13px; }
.monitor-tabs { background: #fff; padding: 0 16px 16px; }
.metric { margin-bottom: 12px; min-height: 92px; }
.metric-label { color: #909399; font-size: 13px; }
.metric-value { margin-top: 12px; color: #303133; font-size: 24px; font-weight: 600; }
.section { margin-top: 4px; }
.chart { height: 320px; }
.toolbar { display: flex; align-items: center; gap: 10px; min-height: 48px; margin-bottom: 8px; }
.toolbar .el-select { width: 220px; }
.base-url { color: #606266; font-size: 12px; overflow-wrap: anywhere; }
.credential-tag { margin-left: 6px; }
.subhead { margin: 24px 0 10px; font-size: 15px; }
.secret-input { margin-top: 16px; }
@media (max-width: 768px) {
  .page { padding: 10px; }
  .toolbar { align-items: stretch; flex-direction: column; }
  .toolbar .el-select { width: 100%; }
  .monitor-tabs { padding: 0 8px 8px; }
}
</style>

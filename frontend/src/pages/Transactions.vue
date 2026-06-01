<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">费用流水</h2>
      <el-button type="primary" @click="dialogVisible = true"><el-icon><Plus /></el-icon>添加流水</el-button>
    </div>

    <!-- 筛选栏 -->
    <el-row :gutter="12" class="filter-row">
      <el-col :span="5">
        <el-select v-model="filter.account_id" placeholder="账号" clearable @change="fetchList">
          <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-select v-model="filter.transaction_type" placeholder="类型" clearable @change="fetchList">
          <el-option label="充值" value="recharge" />
          <el-option label="消费" value="consume" />
          <el-option label="调整" value="adjustment" />
          <el-option label="退款" value="refund" />
        </el-select>
      </el-col>
      <el-col :span="5">
        <el-input v-model="filter.category" placeholder="分类" clearable @change="fetchList" />
      </el-col>
      <el-col :span="8">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DDTHH:mm:ssZ"
          @change="fetchList"
          style="width:100%"
        />
      </el-col>
    </el-row>

    <el-table :data="list" v-loading="loading" border stripe>
      <el-table-column prop="transaction_time" label="时间" width="160">
        <template #default="{ row }">{{ dayjs(row.transaction_time).format('YYYY-MM-DD HH:mm') }}</template>
      </el-table-column>
      <el-table-column label="账号" width="120">
        <template #default="{ row }">{{ accountName(row.account_id) }}</template>
      </el-table-column>
      <el-table-column prop="transaction_type" label="类型" width="80">
        <template #default="{ row }">
          <el-tag :type="txnTagType(row.transaction_type)" size="small">{{ txnLabel(row.transaction_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="amount" label="金额" width="110">
        <template #default="{ row }">
          <span :class="row.transaction_type === 'consume' ? 'consume' : 'recharge'">
            {{ row.transaction_type === 'consume' || row.transaction_type === 'adjustment' ? '-' : '+' }}{{ row.amount }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="balance_after" label="余额" width="100" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="description" label="说明" show-overflow-tooltip />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total"
      layout="total, prev, pager, next" class="pagination" @change="fetchList" />

    <!-- 添加流水 dialog -->
    <el-dialog v-model="dialogVisible" title="添加流水" width="480px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="账号" prop="account_id">
          <el-select v-model="form.account_id" style="width:100%">
            <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型" prop="transaction_type">
          <el-select v-model="form.transaction_type" style="width:100%">
            <el-option label="充值" value="recharge" />
            <el-option label="消费" value="consume" />
            <el-option label="调整（扣减）" value="adjustment" />
            <el-option label="退款" value="refund" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number v-model="form.amount" :min="0.0001" :precision="4" style="width:100%" />
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker v-model="form.transaction_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" style="width:100%" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import dayjs from 'dayjs'
import { ElMessageBox, ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { accountApi } from '@/api/accounts'
import { transactionApi } from '@/api/transactions'
import type { AccountOut, TransactionOut } from '@/types'

const list = ref<TransactionOut[]>([])
const accounts = ref<AccountOut[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dateRange = ref<[string, string] | null>(null)
const filter = reactive({ account_id: '', transaction_type: '', category: '' })

const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ account_id: '', transaction_type: 'consume', amount: 0, transaction_time: '', category: '', description: '' })
const rules = {
  account_id: [{ required: true, message: '请选择账号' }],
  transaction_type: [{ required: true }],
  amount: [{ required: true, type: 'number' as const, min: 0.0001, message: '金额必须大于0' }],
}

async function fetchList() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (filter.account_id) params.account_id = filter.account_id
    if (filter.transaction_type) params.transaction_type = filter.transaction_type
    if (filter.category) params.category = filter.category
    if (dateRange.value) { params.start_time = dateRange.value[0]; params.end_time = dateRange.value[1] }
    const res = await transactionApi.list(params)
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    await transactionApi.create({ ...form, transaction_time: form.transaction_time || undefined })
    dialogVisible.value = false
    ElMessage.success('添加成功')
    await fetchList()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: TransactionOut) {
  await ElMessageBox.confirm('确定删除该条流水记录吗？', '提示', { type: 'warning' })
  await transactionApi.delete(row.id)
  ElMessage.success('已删除')
  await fetchList()
}

function accountName(id: string) {
  return accounts.value.find(a => a.id === id)?.name || id.slice(0, 8)
}
function txnTagType(t: string) {
  return t === 'recharge' ? 'success' : t === 'consume' ? 'danger' : 'info'
}
function txnLabel(t: string) {
  return { recharge: '充值', consume: '消费', adjustment: '调整', refund: '退款' }[t] || t
}

onMounted(async () => {
  const res = await accountApi.list({ page: 1, page_size: 100 })
  accounts.value = res.items
  await fetchList()
})
</script>

<style scoped>
.page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 20px; }
.filter-row { margin-bottom: 16px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
.consume { color: #f56c6c; }
.recharge { color: #67c23a; }
</style>

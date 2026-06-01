<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">预算管理</h2>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增预算</el-button>
    </div>

    <el-row :gutter="12" class="filter-row">
      <el-col :span="6">
        <el-select v-model="filterAccountId" placeholder="账号" clearable @change="fetchList">
          <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-input-number v-model="filterYear" placeholder="年份" :min="2000" :max="2100" @change="fetchList" />
      </el-col>
    </el-row>

    <el-table :data="list" v-loading="loading" border stripe>
      <el-table-column label="账号" width="140">
        <template #default="{ row }">{{ accountName(row.account_id) }}</template>
      </el-table-column>
      <el-table-column prop="year" label="年" width="70" />
      <el-table-column prop="month" label="月" width="60" />
      <el-table-column prop="budget_amount" label="预算金额" width="110">
        <template #default="{ row }">¥{{ row.budget_amount }}</template>
      </el-table-column>
      <el-table-column prop="note" label="备注" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="150">
        <template #default="{ row }">{{ dayjs(row.created_at).format('YYYY-MM-DD') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-model:current-page="page" :page-size="20" :total="total"
      layout="total, prev, pager, next" class="pagination" @current-change="fetchList" />

    <el-dialog v-model="dialogVisible" :title="editTarget ? '编辑预算' : '新增预算'" width="440px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="账号" prop="account_id">
          <el-select v-model="form.account_id" style="width:100%">
            <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="年份" prop="year">
          <el-input-number v-model="form.year" :min="2000" :max="2100" style="width:100%" />
        </el-form-item>
        <el-form-item label="月份" prop="month">
          <el-input-number v-model="form.month" :min="1" :max="12" style="width:100%" />
        </el-form-item>
        <el-form-item label="预算金额" prop="budget_amount">
          <el-input-number v-model="form.budget_amount" :min="0.01" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" rows="2" />
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
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { budgetApi } from '@/api/budgets'
import { accountApi } from '@/api/accounts'
import type { AccountOut, BudgetOut } from '@/types'

const list = ref<BudgetOut[]>([])
const accounts = ref<AccountOut[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const filterAccountId = ref('')
const filterYear = ref<number | null>(dayjs().year())
const dialogVisible = ref(false)
const saving = ref(false)
const editTarget = ref<BudgetOut | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ account_id: '', year: dayjs().year(), month: dayjs().month() + 1, budget_amount: 0, note: '' })
const rules = {
  account_id: [{ required: true, message: '请选择账号' }],
  year: [{ required: true }],
  month: [{ required: true }],
  budget_amount: [{ required: true, type: 'number' as const, min: 0.01 }],
}

async function fetchList() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (filterAccountId.value) params.account_id = filterAccountId.value
    if (filterYear.value) params.year = filterYear.value
    const res = await budgetApi.list(params)
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  Object.assign(form, { account_id: '', year: dayjs().year(), month: dayjs().month() + 1, budget_amount: 0, note: '' })
  dialogVisible.value = true
}
function openEdit(row: BudgetOut) {
  editTarget.value = row
  Object.assign(form, { account_id: row.account_id, year: row.year, month: row.month, budget_amount: Number(row.budget_amount), note: row.note || '' })
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editTarget.value) {
      await budgetApi.update(editTarget.value.id, { budget_amount: form.budget_amount, note: form.note })
    } else {
      await budgetApi.create(form)
    }
    dialogVisible.value = false
    ElMessage.success('保存成功')
    await fetchList()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: BudgetOut) {
  await ElMessageBox.confirm('确定删除该预算？', '提示', { type: 'warning' })
  await budgetApi.delete(row.id)
  ElMessage.success('已删除')
  await fetchList()
}

function accountName(id: string) {
  return accounts.value.find(a => a.id === id)?.name || id.slice(0, 8)
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
</style>

<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">账号管理</h2>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增账号</el-button>
    </div>

    <!-- 筛选栏 -->
    <el-row :gutter="12" class="filter-row">
      <el-col :span="8">
        <el-input v-model="keyword" placeholder="搜索账号名称" clearable @change="fetchList" />
      </el-col>
      <el-col :span="4">
        <el-select v-model="filterStatus" placeholder="状态" clearable @change="fetchList">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
          <el-option label="已归档" value="archived" />
        </el-select>
      </el-col>
    </el-row>

    <el-table :data="list" v-loading="loading" border stripe>
      <el-table-column prop="name" label="账号名称" min-width="120" />
      <el-table-column prop="account_type" label="类型" width="100">
        <template #default="{ row }">{{ typeLabel(row.account_type) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : row.status === 'archived' ? 'info' : 'danger'" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="current_balance" label="当前余额" width="110">
        <template #default="{ row }">¥{{ row.current_balance ?? '-' }}</template>
      </el-table-column>
      <el-table-column prop="tags" label="标签" />
      <el-table-column prop="description" label="说明" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ dayjs(row.created_at).format('YYYY-MM-DD HH:mm') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      class="pagination"
      @change="fetchList"
    />

    <!-- 新增/编辑 dialog -->
    <el-dialog v-model="dialogVisible" :title="editTarget ? '编辑账号' : '新增账号'" width="480px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="类型" prop="account_type">
          <el-select v-model="form.account_type" style="width:100%">
            <el-option label="云服务" value="cloud" />
            <el-option label="订阅" value="subscription" />
            <el-option label="预付费" value="prepaid" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status" v-if="editTarget">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
            <el-option label="归档" value="archived" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="逗号分隔" />
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
import type { AccountOut } from '@/types'

const list = ref<AccountOut[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const keyword = ref('')
const filterStatus = ref('')

const dialogVisible = ref(false)
const saving = ref(false)
const editTarget = ref<AccountOut | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', account_type: 'other', status: 'active', tags: '', description: '' })
const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

async function fetchList() {
  loading.value = true
  try {
    const res = await accountApi.list({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined, status: filterStatus.value || undefined })
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  Object.assign(form, { name: '', account_type: 'other', status: 'active', tags: '', description: '' })
  dialogVisible.value = true
}

function openEdit(row: AccountOut) {
  editTarget.value = row
  Object.assign(form, { name: row.name, account_type: row.account_type, status: row.status, tags: row.tags || '', description: row.description || '' })
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editTarget.value) {
      await accountApi.update(editTarget.value.id, form)
    } else {
      await accountApi.create(form)
    }
    dialogVisible.value = false
    ElMessage.success('保存成功')
    await fetchList()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: AccountOut) {
  await ElMessageBox.confirm(`确定要删除账号【${row.name}】吗？`, '提示', { type: 'warning' })
  await accountApi.delete(row.id)
  ElMessage.success('已删除')
  await fetchList()
}

function typeLabel(t: string) {
  return { cloud: '云服务', subscription: '订阅', prepaid: '预付费', other: '其他' }[t] || t
}
function statusLabel(s: string) {
  return { active: '启用', inactive: '停用', archived: '归档' }[s] || s
}

onMounted(fetchList)
</script>

<style scoped>
.page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 20px; }
.filter-row { margin-bottom: 16px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
</style>

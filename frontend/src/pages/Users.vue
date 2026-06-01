<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">用户管理</h2>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增用户</el-button>
    </div>

    <el-table :data="list" v-loading="loading" border stripe>
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="email" label="邮箱" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'operator' ? 'warning' : 'info'" size="small">
            {{ { admin: '管理员', operator: '运营', viewer: '只读' }[row.role] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="150">
        <template #default="{ row }">{{ dayjs(row.created_at).format('YYYY-MM-DD HH:mm') }}</template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="上次登录" width="150">
        <template #default="{ row }">{{ row.last_login_at ? dayjs(row.last_login_at).format('MM-DD HH:mm') : '从未' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-model:current-page="page" :page-size="20" :total="total"
      layout="total, prev, pager, next" class="pagination" @current-change="fetchList" />

    <el-dialog v-model="dialogVisible" :title="editTarget ? '编辑用户' : '新增用户'" width="440px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <template v-if="!editTarget">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="form.email" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" show-password />
          </el-form-item>
        </template>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width:100%">
            <el-option label="管理员" value="admin" />
            <el-option label="运营" value="operator" />
            <el-option label="只读" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" v-if="editTarget">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
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
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { userApi } from '@/api/users'
import type { UserOut } from '@/types'

const list = ref<UserOut[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editTarget = ref<UserOut | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ username: '', email: '', password: '', role: 'viewer', status: 'active' })
const rules = {
  username: [{ required: true }],
  email: [{ required: true, type: 'email' as const }],
  password: [{ required: true, min: 8 }],
}

async function fetchList() {
  loading.value = true
  try {
    const res = await userApi.list({ page: page.value, page_size: 20 })
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  Object.assign(form, { username: '', email: '', password: '', role: 'viewer', status: 'active' })
  dialogVisible.value = true
}
function openEdit(row: UserOut) {
  editTarget.value = row
  Object.assign(form, { username: row.username, email: row.email, role: row.role, status: row.status, password: '' })
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editTarget.value) {
      await userApi.update(editTarget.value.id, { role: form.role, status: form.status, email: form.email })
    } else {
      await userApi.create(form)
    }
    dialogVisible.value = false
    ElMessage.success('保存成功')
    await fetchList()
  } finally {
    saving.value = false
  }
}

onMounted(fetchList)
</script>

<style scoped>
.page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 20px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
</style>

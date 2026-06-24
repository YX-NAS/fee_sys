<template>
  <div class="notif-panel">
    <div class="notif-actions">
      <el-radio-group v-model="readFilter" size="small" @change="onFilterChange">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="false">未读</el-radio-button>
        <el-radio-button value="true">已读</el-radio-button>
      </el-radio-group>
      <el-button size="small" @click="markAll" :disabled="!unreadCount">全部已读</el-button>
    </div>
    <el-scrollbar max-height="calc(100vh - 160px)">
      <div v-if="items.length === 0" class="empty">{{ readFilter === 'false' ? '暂无未读通知' : '暂无通知' }}</div>
      <div
        v-for="n in items"
        :key="n.id"
        class="notif-item"
        :class="{ unread: !n.is_read }"
        @click="markOne(n)"
      >
        <div class="notif-title">
          <span v-if="isCritical(n.title)" class="severity-dot critical" />
          <span v-else-if="isWarning(n.title)" class="severity-dot warning" />
          {{ n.title }}
        </div>
        <div class="notif-content">{{ n.content }}</div>
        <div class="notif-time">{{ dayjs(n.created_at).format('MM-DD HH:mm') }}</div>
      </div>
    </el-scrollbar>
    <div v-if="total > items.length" class="load-more">
      <el-button size="small" @click="loadMore">加载更多</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import dayjs from 'dayjs'
import { notificationApi } from '@/api/notifications'
import { useNotificationStore } from '@/stores/notification'
import type { NotificationOut } from '@/types'

const emit = defineEmits(['close'])
const notifStore = useNotificationStore()
const items = ref<NotificationOut[]>([])
const total = ref(0)
const page = ref(1)
const readFilter = ref('')
const unreadCount = ref(0)
let refreshTimer: ReturnType<typeof setInterval> | null = null

async function load() {
  const params: Record<string, unknown> = { page: page.value, page_size: 20 }
  if (readFilter.value === 'true') params.is_read = true
  else if (readFilter.value === 'false') params.is_read = false
  const res = await notificationApi.list(params)
  if (page.value === 1) items.value = res.items
  else items.value.push(...res.items)
  total.value = res.total
  unreadCount.value = notifStore.unreadCount
}

async function markOne(n: NotificationOut) {
  if (!n.is_read) {
    await notificationApi.markRead(n.id)
    n.is_read = true
    notifStore.unreadCount = Math.max(0, notifStore.unreadCount - 1)
    unreadCount.value = notifStore.unreadCount
  }
}

async function markAll() {
  await notificationApi.markAllRead()
  items.value.forEach(n => { n.is_read = true })
  notifStore.unreadCount = 0
  unreadCount.value = 0
}

async function loadMore() {
  page.value++
  await load()
}

function onFilterChange() {
  page.value = 1
  load()
}

function isCritical(title: string) { return /CRITICAL|严重/.test(title) }
function isWarning(title: string) { return /WARNING|警告/.test(title) }

onMounted(() => {
  load()
  refreshTimer = setInterval(() => { if (readFilter.value !== 'true') load() }, 30000)
})
onBeforeUnmount(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<style scoped>
.notif-actions { display: flex; align-items: center; justify-content: space-between; padding: 8px 0 12px; }
.notif-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; cursor: pointer; }
.notif-item.unread .notif-title { font-weight: bold; color: #303133; }
.notif-title { font-size: 14px; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
.notif-content { font-size: 12px; color: #606266; margin-bottom: 4px; }
.notif-time { font-size: 12px; color: #909399; }
.empty { text-align: center; color: #909399; padding: 40px 0; }
.load-more { text-align: center; padding: 12px 0; }
.severity-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.severity-dot.critical { background: #f56c6c; }
.severity-dot.warning { background: #e6a23c; }
</style>

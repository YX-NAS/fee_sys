<template>
  <div class="notif-panel">
    <div class="notif-actions">
      <el-button size="small" @click="markAll">全部已读</el-button>
    </div>
    <el-scrollbar max-height="calc(100vh - 120px)">
      <div v-if="items.length === 0" class="empty">暂无通知</div>
      <div
        v-for="n in items"
        :key="n.id"
        class="notif-item"
        :class="{ unread: !n.is_read }"
        @click="markOne(n)"
      >
        <div class="notif-title">{{ n.title }}</div>
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
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { notificationApi } from '@/api/notifications'
import { useNotificationStore } from '@/stores/notification'
import type { NotificationOut } from '@/types'

const emit = defineEmits(['close'])
const notifStore = useNotificationStore()
const items = ref<NotificationOut[]>([])
const total = ref(0)
const page = ref(1)

async function load() {
  const res = await notificationApi.list({ page: page.value, page_size: 20 })
  if (page.value === 1) items.value = res.items
  else items.value.push(...res.items)
  total.value = res.total
}

async function markOne(n: NotificationOut) {
  if (!n.is_read) {
    await notificationApi.markRead(n.id)
    n.is_read = true
    notifStore.unreadCount = Math.max(0, notifStore.unreadCount - 1)
  }
}

async function markAll() {
  await notificationApi.markAllRead()
  items.value.forEach(n => { n.is_read = true })
  notifStore.unreadCount = 0
}

async function loadMore() {
  page.value++
  await load()
}

onMounted(load)
</script>

<style scoped>
.notif-actions { padding: 8px 0 12px; text-align: right; }
.notif-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; cursor: pointer; }
.notif-item.unread .notif-title { font-weight: bold; color: #303133; }
.notif-title { font-size: 14px; margin-bottom: 4px; }
.notif-content { font-size: 12px; color: #606266; margin-bottom: 4px; }
.notif-time { font-size: 12px; color: #909399; }
.empty { text-align: center; color: #909399; padding: 40px 0; }
.load-more { text-align: center; padding: 12px 0; }
</style>

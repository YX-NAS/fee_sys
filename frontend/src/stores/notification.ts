import { defineStore } from 'pinia'
import { ref } from 'vue'
import { notificationApi } from '@/api/notifications'

export const useNotificationStore = defineStore('notification', () => {
  const unreadCount = ref(0)

  async function fetchUnreadCount() {
    try {
      const data = await notificationApi.getUnreadCount()
      unreadCount.value = data.count
    } catch {
      // silently ignore
    }
  }

  return { unreadCount, fetchUnreadCount }
})

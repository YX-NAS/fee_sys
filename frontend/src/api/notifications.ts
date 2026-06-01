import http from './http'
import type { NotificationOut, PagedResponse } from '@/types'

export const notificationApi = {
  list: (params?: object): Promise<PagedResponse<NotificationOut>> => http.get('/api/notifications', { params }),
  getUnreadCount: (): Promise<{ count: number }> => http.get('/api/notifications/unread-count'),
  markRead: (id: string): Promise<NotificationOut> => http.put(`/api/notifications/${id}/read`),
  markAllRead: () => http.put('/api/notifications/read-all'),
}

import http from './http'
import type { AlertConfigOut, AlertEventOut, AlertSummary, PagedResponse } from '@/types'

export const alertApi = {
  listConfigs: (params?: object): Promise<PagedResponse<AlertConfigOut>> => http.get('/api/alerts/configs', { params }),
  createConfig: (data: object): Promise<AlertConfigOut> => http.post('/api/alerts/configs', data),
  updateConfig: (id: string, data: object): Promise<AlertConfigOut> => http.put(`/api/alerts/configs/${id}`, data),
  deleteConfig: (id: string) => http.delete(`/api/alerts/configs/${id}`),

  listEvents: (params?: object): Promise<PagedResponse<AlertEventOut>> => http.get('/api/alerts/events', { params }),
  acknowledgeEvent: (id: string): Promise<AlertEventOut> => http.post(`/api/alerts/events/${id}/acknowledge`),
  retryEvent: (id: string): Promise<AlertEventOut> => http.post(`/api/alerts/events/${id}/retry`),
  batchAcknowledge: (eventIds: string[]): Promise<{ acknowledged: number }> =>
    http.post('/api/alerts/events/batch-acknowledge', { event_ids: eventIds }),

  summary: (): Promise<AlertSummary> => http.get('/api/alerts/summary'),
}

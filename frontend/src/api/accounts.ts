import http from './http'
import type { AccountOut, PagedResponse } from '@/types'

export const accountApi = {
  list: (params: object): Promise<PagedResponse<AccountOut>> => http.get('/api/accounts', { params }),
  get: (id: string): Promise<AccountOut> => http.get(`/api/accounts/${id}`),
  create: (data: object): Promise<AccountOut> => http.post('/api/accounts', data),
  update: (id: string, data: object): Promise<AccountOut> => http.put(`/api/accounts/${id}`, data),
  delete: (id: string) => http.delete(`/api/accounts/${id}`),
}

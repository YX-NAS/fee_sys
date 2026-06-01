import http from './http'
import type { TransactionOut, PagedResponse } from '@/types'

export const transactionApi = {
  list: (params: object): Promise<PagedResponse<TransactionOut>> => http.get('/api/transactions', { params }),
  get: (id: string): Promise<TransactionOut> => http.get(`/api/transactions/${id}`),
  create: (data: object): Promise<TransactionOut> => http.post('/api/transactions', data),
  delete: (id: string) => http.delete(`/api/transactions/${id}`),
}

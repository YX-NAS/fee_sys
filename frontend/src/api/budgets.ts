import http from './http'
import type { BudgetOut, PagedResponse } from '@/types'

export const budgetApi = {
  list: (params?: object): Promise<PagedResponse<BudgetOut>> => http.get('/api/budgets', { params }),
  create: (data: object): Promise<BudgetOut> => http.post('/api/budgets', data),
  update: (id: string, data: object): Promise<BudgetOut> => http.put(`/api/budgets/${id}`, data),
  delete: (id: string) => http.delete(`/api/budgets/${id}`),
}

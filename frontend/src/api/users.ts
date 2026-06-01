import http from './http'
import type { UserOut, PagedResponse } from '@/types'

export const userApi = {
  list: (params?: object): Promise<PagedResponse<UserOut>> => http.get('/api/users', { params }),
  create: (data: object): Promise<UserOut> => http.post('/api/users', data),
  update: (id: string, data: object): Promise<UserOut> => http.put(`/api/users/${id}`, data),
}

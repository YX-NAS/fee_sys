import http from './http'
import type { TokenResponse, UserOut } from '@/types'

export const authApi = {
  login: (username: string, password: string): Promise<TokenResponse> => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return http.post('/api/auth/login', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  },
  refresh: (refreshToken: string): Promise<TokenResponse> =>
    http.post('/api/auth/refresh', { refresh_token: refreshToken }),
  me: (): Promise<UserOut> => http.get('/api/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    http.put('/api/auth/me/password', { old_password, new_password }),
}

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserOut, TokenResponse } from '@/types'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<UserOut | null>(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username: string, password: string) {
    const resp: TokenResponse = await authApi.login(username, password)
    token.value = resp.access_token
    refreshToken.value = resp.refresh_token
    user.value = resp.user
    localStorage.setItem('access_token', resp.access_token)
    localStorage.setItem('refresh_token', resp.refresh_token)
    localStorage.setItem('user', JSON.stringify(resp.user))
  }

  function logout() {
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  }

  async function tryRefresh(): Promise<boolean> {
    if (!refreshToken.value) return false
    try {
      const resp: TokenResponse = await authApi.refresh(refreshToken.value)
      token.value = resp.access_token
      refreshToken.value = resp.refresh_token
      user.value = resp.user
      localStorage.setItem('access_token', resp.access_token)
      localStorage.setItem('refresh_token', resp.refresh_token)
      localStorage.setItem('user', JSON.stringify(resp.user))
      return true
    } catch {
      logout()
      return false
    }
  }

  return { token, refreshToken, user, isLoggedIn, isAdmin, login, logout, tryRefresh }
})

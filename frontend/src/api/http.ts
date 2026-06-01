import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => res.data,
  async (error) => {
    if (error.response?.status === 401) {
      // 尝试刷新 token
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken && !error.config._retry) {
        error.config._retry = true
        try {
          const { useAuthStore } = await import('@/stores/auth')
          const auth = useAuthStore()
          const ok = await auth.tryRefresh()
          if (ok) {
            error.config.headers.Authorization = `Bearer ${localStorage.getItem('access_token')}`
            return http(error.config)
          }
        } catch {
          // fall through to redirect
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    } else {
      const msg = error.response?.data?.detail || error.message || '请求失败'
      ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
    return Promise.reject(error)
  }
)

export default http

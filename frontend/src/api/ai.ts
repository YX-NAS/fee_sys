import http from './http'
import type {
  AIAccount, AIDailyUsage, AIGatewayKey, AIOverview, AIPrice,
  AIProviderAPICredential, AIAlertRuleOut, AIAlertEventOut,
} from '@/types'

export const aiApi = {
  accounts: () => http.get<unknown, AIAccount[]>('/api/ai/accounts'),
  createAccount: (data: Record<string, unknown>) => http.post<unknown, AIAccount>('/api/ai/accounts', data),
  updateAccount: (id: string, data: Record<string, unknown>) => http.put<unknown, AIAccount>(`/api/ai/accounts/${id}`, data),
  deleteAccount: (id: string) => http.delete(`/api/ai/accounts/${id}`),
  testAccount: (id: string) => http.post(`/api/ai/accounts/${id}/test`),
  apiCredentials: (accountId: string) =>
    http.get<unknown, AIProviderAPICredential[]>(`/api/ai/accounts/${accountId}/api-credentials`),
  createApiCredential: (accountId: string, data: Record<string, unknown>) =>
    http.post<unknown, AIProviderAPICredential>(`/api/ai/accounts/${accountId}/api-credentials`, data),
  updateApiCredential: (accountId: string, id: string, data: Record<string, unknown>) =>
    http.put<unknown, AIProviderAPICredential>(`/api/ai/accounts/${accountId}/api-credentials/${id}`, data),
  deleteApiCredential: (accountId: string, id: string) =>
    http.delete(`/api/ai/accounts/${accountId}/api-credentials/${id}`),
  testApiCredential: (accountId: string, id: string) =>
    http.post(`/api/ai/accounts/${accountId}/api-credentials/${id}/test`),
  syncAccount: (id: string, data: { start_date: string; end_date: string }) => http.post(`/api/ai/accounts/${id}/sync`, data),
  syncBalance: (id: string) => http.post(`/api/ai/accounts/${id}/sync-balance`),
  overview: () => http.get<unknown, AIOverview>('/api/ai/overview'),
  dailyUsage: (params: Record<string, unknown>) => http.get<unknown, AIDailyUsage[]>('/api/ai/usage/daily', { params }),
  models: (params: Record<string, unknown>) => http.get('/api/ai/models', { params }),
  balances: (params: Record<string, unknown> = {}) => http.get('/api/ai/balances', { params }),
  syncRuns: () => http.get<unknown, any[]>('/api/ai/sync-runs'),
  keys: (accountId: string) => http.get<unknown, AIGatewayKey[]>(`/api/ai/accounts/${accountId}/gateway-keys`),
  createKey: (accountId: string, data: Record<string, unknown>) =>
    http.post<unknown, AIGatewayKey>(`/api/ai/accounts/${accountId}/gateway-keys`, data),
  disableKey: (id: string) => http.post(`/api/ai/gateway-keys/${id}/disable`),
  prices: () => http.get<unknown, AIPrice[]>('/api/ai/prices'),
  createPrice: (data: Record<string, unknown>) => http.post<unknown, AIPrice>('/api/ai/prices', data),
  alerts: () => http.get<unknown, { rules: AIAlertRuleOut[]; events: AIAlertEventOut[] }>('/api/ai/alerts'),
  updateAlert: (accountId: string, type: string, data: Record<string, unknown>) =>
    http.put(`/api/ai/accounts/${accountId}/alerts/${type}`, data),
  acknowledgeAlert: (id: string) => http.post(`/api/ai/alerts/${id}/acknowledge`),
}

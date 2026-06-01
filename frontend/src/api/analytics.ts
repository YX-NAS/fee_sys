import http from './http'
import type { AnalyticsSummary, BudgetVarianceResult, CategoryStat, ComparisonResult, TrendPoint } from '@/types'

export const analyticsApi = {
  getSummary: (accountId: string): Promise<AnalyticsSummary> => http.get(`/api/analytics/summary/${accountId}`),
  getTrend: (accountId: string, params: object): Promise<TrendPoint[]> =>
    http.get(`/api/analytics/trend/${accountId}`, { params }),
  getCategories: (accountId: string, params: object): Promise<CategoryStat[]> =>
    http.get(`/api/analytics/categories/${accountId}`, { params }),
  getComparison: (accountId: string, params: object): Promise<ComparisonResult> =>
    http.get(`/api/analytics/comparison/${accountId}`, { params }),
  getBudgetVariance: (accountId: string, params: object): Promise<BudgetVarianceResult | null> =>
    http.get(`/api/analytics/budget-variance/${accountId}`, { params }),
}

<template>
  <div class="page">
    <h2 class="page-title">费用分析</h2>

    <!-- 筛选 -->
    <el-row :gutter="12" class="filter-row">
      <el-col :span="6">
        <el-select v-model="accountId" placeholder="选择账号" @change="loadAll">
          <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-col>
      <el-col :span="8">
        <el-date-picker v-model="dateRange" type="monthrange" range-separator="至"
          start-placeholder="开始月" end-placeholder="结束月" value-format="YYYY-MM-DDTHH:mm:ssZ"
          @change="loadAll" style="width:100%" />
      </el-col>
      <el-col :span="4">
        <el-select v-model="granularity" @change="loadTrend">
          <el-option label="按天" value="day" />
          <el-option label="按周" value="week" />
          <el-option label="按月" value="month" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-select v-model="compareType" placeholder="同比/环比" @change="loadComparison">
          <el-option label="环比" value="mom" />
          <el-option label="同比" value="yoy" />
        </el-select>
      </el-col>
    </el-row>

    <el-row :gutter="16" v-if="accountId">
      <!-- 趋势图 -->
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>消费/充值趋势</template>
          <div ref="trendChartEl" style="height:300px" />
        </el-card>
      </el-col>

      <!-- 分类饼图 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>消费分类分布</template>
          <div ref="categoryChartEl" style="height:300px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px" v-if="accountId">
      <!-- 同比/环比 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>{{ compareType === 'mom' ? '环比对比' : '同比对比' }}</template>
          <div v-if="comparison" class="comparison-box">
            <div class="cmp-row">
              <span class="cmp-label">本期（{{ comparison.current_period }}）</span>
              <span class="cmp-val">¥{{ comparison.current_amount }}</span>
            </div>
            <div class="cmp-row">
              <span class="cmp-label">对比期（{{ comparison.compare_period }}）</span>
              <span class="cmp-val">¥{{ comparison.compare_amount }}</span>
            </div>
            <div class="cmp-row">
              <span class="cmp-label">变化额</span>
              <span class="cmp-val" :class="Number(comparison.change_amount) > 0 ? 'consume' : 'recharge'">
                {{ Number(comparison.change_amount) > 0 ? '+' : '' }}{{ comparison.change_amount }}
              </span>
            </div>
            <div class="cmp-row">
              <span class="cmp-label">变化率</span>
              <span class="cmp-val" :class="comparison.change_rate !== null && comparison.change_rate > 0 ? 'consume' : 'recharge'">
                {{ comparison.change_rate !== null ? (comparison.change_rate * 100).toFixed(1) + '%' : 'N/A' }}
              </span>
            </div>
          </div>
          <div v-else class="empty-hint">请选择账号和月份</div>
        </el-card>
      </el-col>

      <!-- 预算偏差 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>预算偏差（{{ cmpYear }}-{{ String(cmpMonth).padStart(2, '0') }}）</template>
          <div v-if="budgetVariance" class="comparison-box">
            <div class="cmp-row">
              <span class="cmp-label">预算金额</span>
              <span class="cmp-val">¥{{ budgetVariance.budget_amount }}</span>
            </div>
            <div class="cmp-row">
              <span class="cmp-label">实际消费</span>
              <span class="cmp-val">¥{{ budgetVariance.actual_amount }}</span>
            </div>
            <div class="cmp-row">
              <span class="cmp-label">偏差额</span>
              <span class="cmp-val" :class="Number(budgetVariance.variance) > 0 ? 'consume' : 'recharge'">
                {{ Number(budgetVariance.variance) > 0 ? '+' : '' }}{{ budgetVariance.variance }}
              </span>
            </div>
            <div class="cmp-row">
              <span class="cmp-label">偏差率</span>
              <span class="cmp-val" :class="budgetVariance.variance_rate !== null && budgetVariance.variance_rate > 0 ? 'consume' : 'recharge'">
                {{ budgetVariance.variance_rate !== null ? (budgetVariance.variance_rate * 100).toFixed(1) + '%' : 'N/A' }}
              </span>
            </div>
          </div>
          <div v-else class="empty-hint">该月暂无预算数据</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { accountApi } from '@/api/accounts'
import { analyticsApi } from '@/api/analytics'
import type { AccountOut, ComparisonResult, BudgetVarianceResult, TrendPoint, CategoryStat } from '@/types'

const accounts = ref<AccountOut[]>([])
const accountId = ref('')
const dateRange = ref<[string, string] | null>(null)
const granularity = ref('month')
const compareType = ref('mom')
const cmpYear = ref(dayjs().year())
const cmpMonth = ref(dayjs().month() + 1)
const comparison = ref<ComparisonResult | null>(null)
const budgetVariance = ref<BudgetVarianceResult | null>(null)

const trendChartEl = ref<HTMLElement>()
const categoryChartEl = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let categoryChart: echarts.ECharts | null = null

async function loadAll() {
  if (!accountId.value) return
  await Promise.all([loadTrend(), loadCategories(), loadComparison(), loadBudgetVariance()])
}

async function loadTrend() {
  if (!accountId.value || !dateRange.value) return
  const rows: TrendPoint[] = await analyticsApi.getTrend(accountId.value, {
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
    granularity: granularity.value,
  })
  await nextTick()
  if (!trendChart && trendChartEl.value) trendChart = echarts.init(trendChartEl.value)
  trendChart?.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['消费', '充值'] },
    xAxis: { type: 'category', data: rows.map(r => r.period) },
    yAxis: { type: 'value' },
    series: [
      { name: '消费', type: 'bar', data: rows.map(r => r.total_consume), itemStyle: { color: '#f56c6c' } },
      { name: '充值', type: 'bar', data: rows.map(r => r.total_recharge), itemStyle: { color: '#67c23a' } },
    ],
  })
}

async function loadCategories() {
  if (!accountId.value || !dateRange.value) return
  const rows: CategoryStat[] = await analyticsApi.getCategories(accountId.value, {
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
  })
  await nextTick()
  if (!categoryChart && categoryChartEl.value) categoryChart = echarts.init(categoryChartEl.value)
  categoryChart?.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{
      type: 'pie', radius: '70%',
      data: rows.map(r => ({ name: r.category, value: r.total })),
    }],
  })
}

async function loadComparison() {
  if (!accountId.value) return
  comparison.value = await analyticsApi.getComparison(accountId.value, {
    year: cmpYear.value, month: cmpMonth.value, compare_type: compareType.value,
  })
}

async function loadBudgetVariance() {
  if (!accountId.value) return
  budgetVariance.value = await analyticsApi.getBudgetVariance(accountId.value, {
    year: cmpYear.value, month: cmpMonth.value,
  })
}

onMounted(async () => {
  const res = await accountApi.list({ page: 1, page_size: 100, status: 'active' })
  accounts.value = res.items
  // 默认近6个月
  dateRange.value = [
    dayjs().subtract(5, 'month').startOf('month').toISOString(),
    dayjs().endOf('month').toISOString(),
  ]
})
</script>

<style scoped>
.page { padding: 20px; }
.page-title { margin: 0 0 16px; font-size: 20px; }
.filter-row { margin-bottom: 16px; }
.comparison-box { padding: 8px 0; }
.cmp-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.cmp-label { color: #606266; }
.cmp-val { font-weight: bold; }
.empty-hint { text-align: center; color: #909399; padding: 40px 0; }
.consume { color: #f56c6c; }
.recharge { color: #67c23a; }
</style>

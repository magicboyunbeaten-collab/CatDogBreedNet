<template>
  <div class="stats-view">
    <el-page-header :icon="null" title="" @back="onBack">
      <template #content>
        <span class="page-title">识别统计</span>
      </template>
    </el-page-header>

    <el-text class="page-desc" type="info">
      以下统计完全来自后端数据库的真实识别记录，不包含任何演示数据。
    </el-text>

    <el-row v-loading="loading" :gutter="16">
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">总识别次数</div>
          <div class="stat-value">{{ stats.total_predictions ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">平均推理耗时</div>
          <div class="stat-value">
            {{ stats.avg_inference_ms == null ? '-' : stats.avg_inference_ms.toFixed(2) + ' ms' }}
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">覆盖品种数</div>
          <div class="stat-value">{{ stats.breed_distribution?.length ?? 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="stats-error"
    />

    <el-row v-if="!errorMessage" :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>
            <span>品种分布（Top {{ breedTopN }}）</span>
          </template>
          <div v-if="loading" class="chart-placeholder">加载中…</div>
          <div v-else-if="hasData" ref="breedChartRef" class="chart"></div>
          <el-empty v-else description="暂无识别记录" :image-size="80" />
          <div v-if="hasData && !loading" class="chart-caption">
            合计 {{ distributionTotal }} 次（按识别次数降序，最多 {{ TOP_BREEDS_LIMIT }} 个品种）
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>
            <span>每日识别趋势（UTC）</span>
          </template>
          <div v-if="loading" class="chart-placeholder">加载中…</div>
          <div v-else-if="hasData" ref="trendChartRef" class="chart"></div>
          <el-empty v-else description="暂无识别记录" :image-size="80" />
          <div v-if="hasData && !loading" class="chart-caption">
            近 {{ TREND_DAYS }} 天合计 {{ trendTotal }} 次
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { fetchStats } from '../api/stats'
import { goBack } from '../utils/navigation'
import { getBreedDisplayName } from '../utils/breedNames'

const router = useRouter()

const stats = ref({
  total_predictions: 0,
  breed_distribution: [],
  daily_trend: [],
  avg_inference_ms: null
})
const loading = ref(false)
const errorMessage = ref('')
const breedChartRef = ref(null)
const trendChartRef = ref(null)
let breedChart = null
let trendChart = null

const hasData = computed(() => stats.value.total_predictions > 0)

// 展示上限，与后端 settings 默认值对应（STATS_TOP_BREEDS / STATS_TREND_DAYS）
const TOP_BREEDS_LIMIT = 10
const TREND_DAYS = 30

const breedTopN = computed(() =>
  Math.min(stats.value.breed_distribution?.length || 0, TOP_BREEDS_LIMIT))
const distributionTotal = computed(() =>
  (stats.value.breed_distribution || []).reduce((sum, row) => sum + row.count, 0))
const trendTotal = computed(() =>
  (stats.value.daily_trend || []).reduce((sum, row) => sum + row.count, 0))

// 返回上一个站内页面；直接打开本页时回退到默认识别页
function onBack() {
  goBack(router)
}

function disposeCharts() {
  if (breedChart) {
    breedChart.dispose()
    breedChart = null
  }
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
}

let renderedSignature = null

function renderCharts() {
  if (!hasData.value) {
    renderedSignature = null
    disposeCharts()
    return
  }
  // 相同数据不重复初始化（loadStats 与 hasData watcher 可能先后触发）
  const signature = JSON.stringify([
    stats.value.breed_distribution,
    stats.value.daily_trend
  ])
  if (signature === renderedSignature) return
  renderedSignature = signature

  disposeCharts()

  const distribution = stats.value.breed_distribution || []
  if (breedChartRef.value) {
    breedChart = echarts.init(breedChartRef.value)
    breedChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: 'category', data: distribution.map((row) => getBreedDisplayName(row.breed)),
               axisLabel: { rotate: distribution.length > 4 ? 35 : 0, interval: 0 } },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{
        name: '识别次数',
        type: 'bar',
        data: distribution.map((row) => row.count),
        itemStyle: { color: '#409eff' }
      }]
    })
  }

  const trend = stats.value.daily_trend || []
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: 'category', data: trend.map((row) => row.date),
               boundaryGap: false },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{
        name: '识别次数',
        type: 'line',
        smooth: true,
        data: trend.map((row) => row.count),
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#67c23a' }
      }]
    })
  }
}

async function loadStats() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await fetchStats()
    stats.value = {
      total_predictions: data.total_predictions || 0,
      breed_distribution: data.breed_distribution || [],
      daily_trend: data.daily_trend || [],
      avg_inference_ms: data.avg_inference_ms
    }
  } catch (error) {
    errorMessage.value = error.message || '统计数据加载失败'
  } finally {
    // 先解除 loading，让图表容器完成渲染，再初始化 ECharts。
    // （曾经的缺陷：在 loading 仍为 true 时调用 renderCharts，
    //  图表行被 v-if 隐藏、容器不存在，echarts.init 从未执行。）
    loading.value = false
  }
  await nextTick()
  renderCharts()
}

function handleResize() {
  breedChart?.resize()
  trendChart?.resize()
}

watch(hasData, (value) => {
  // loading 期间容器尚未渲染，由 loadStats 在 loading 解除后统一初始化，
  // 避免 watcher 与 loadStats 重复 init/dispose。
  if (value && !loading.value) nextTick(renderCharts)
})

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})
</script>

<style scoped>
.page-title {
  font-size: 20px;
  font-weight: 600;
}

.page-desc {
  display: block;
  margin: 12px 0 20px;
}

.stat-card {
  text-align: center;
  margin-bottom: 16px;
}

.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  margin-top: 8px;
  font-variant-numeric: tabular-nums;
}

.stats-error {
  margin-bottom: 16px;
}

.chart {
  height: 320px;
}

.chart-placeholder {
  height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
}

.chart-caption {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

</style>

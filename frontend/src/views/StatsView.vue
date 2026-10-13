<template>
  <div class="stats-view">
    <el-page-header :icon="null" title="">
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

    <el-row v-if="!loading && !errorMessage" :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>
            <span>品种分布（Top {{ stats.breed_distribution?.length ?? 0 }}）</span>
          </template>
          <div v-if="hasData" ref="breedChartRef" class="chart"></div>
          <el-empty v-else description="暂无识别记录" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>
            <span>每日识别趋势（UTC）</span>
          </template>
          <div v-if="hasData" ref="trendChartRef" class="chart"></div>
          <el-empty v-else description="暂无识别记录" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { fetchStats } from '../api/stats'

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

function renderCharts() {
  disposeCharts()
  if (!hasData.value) return

  const distribution = stats.value.breed_distribution || []
  if (breedChartRef.value) {
    breedChart = echarts.init(breedChartRef.value)
    breedChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: 'category', data: distribution.map((row) => row.breed),
               axisLabel: { rotate: distribution.length > 4 ? 35 : 0 } },
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
    await nextTick()
    renderCharts()
  } catch (error) {
    errorMessage.value = error.message || '统计数据加载失败'
  } finally {
    loading.value = false
  }
}

function handleResize() {
  breedChart?.resize()
  trendChart?.resize()
}

watch(hasData, (value) => {
  if (value) nextTick(renderCharts)
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
</style>

/**
 * StatsView 组件测试：统计图表空白缺陷的回归 + 口径一致性。
 *
 * 覆盖：
 *  A. 正常数据：标题 Top N、ECharts 初始化时机与次数、中文品种名、计数数据
 *  B. 超过 10 个品种 / 多个日期
 *  C. 空数据：空状态而非空白区域，且不初始化图表
 *  D. 加载失败：错误提示，不渲染图表
 *  E. 页面数字与后端口径一致（总次数 = 分布合计；趋势为近 30 天窗口合计）
 *  F. Back 按钮：直接打开 /stats 时回退到 /predict
 *
 * echarts 在 jsdom 中无 canvas 实现，这里 mock init/setOption/dispose，
 * 验证本组件的渲染时机与数据映射；真实 ECharts 渲染由 Chrome 联调验证。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createWebHistory } from 'vue-router'

const { instances, fetchStatsMock } = vi.hoisted(() => ({
  instances: [],
  fetchStatsMock: vi.fn()
}))

vi.mock('echarts', () => ({
  init: (dom) => {
    const inst = { dom, setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() }
    instances.push(inst)
    return inst
  }
}))
vi.mock('../src/api/stats', () => ({ fetchStats: fetchStatsMock }))

const StatsView = (await import('../src/views/StatsView.vue')).default

const ROUTES = [
  { path: '/', redirect: '/predict' },
  { path: '/predict', name: 'predict', component: { template: '<div>predict</div>' } },
  { path: '/history', name: 'history', component: { template: '<div>history</div>' } },
  { path: '/stats', name: 'stats', component: { template: '<div>stats</div>' } }
]

function mountAt(path) {
  // 模拟“直接打开某个 URL”：清空 history.state，无站内返回历史
  window.history.replaceState(null, '', path)
  const router = createRouter({ history: createWebHistory(), routes: ROUTES })
  const wrapper = mount(StatsView, {
    global: { plugins: [ElementPlus, router] }
  })
  return { wrapper, router }
}

const NORMAL_STATS = {
  success: true,
  total_predictions: 8,
  breed_distribution: [
    { breed: 'beagle', count: 5 },
    { breed: 'Siamese', count: 2 },
    { breed: 'havanese', count: 1 }
  ],
  daily_trend: [
    { date: '2026-10-12', count: 3 },
    { date: '2026-10-13', count: 5 }
  ],
  avg_inference_ms: 11.5
}

afterEach(() => {
  instances.length = 0
  fetchStatsMock.mockReset()
  vi.restoreAllMocks()
})

describe('StatsView 图表渲染（原缺陷：两张图空白）', () => {
  it('正常数据：loading 解除后初始化两张图表，标题显示具体 Top N', async () => {
    fetchStatsMock.mockResolvedValue(NORMAL_STATS)
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('品种分布（Top 3）')
    // 两张图表都必须初始化（原缺陷：0 次）
    expect(instances.length).toBe(2)
    expect(instances[0].setOption).toHaveBeenCalledTimes(1)
    expect(instances[1].setOption).toHaveBeenCalledTimes(1)
    // 不再显示“加载中”占位或空状态
    expect(wrapper.text()).not.toContain('加载中')
    expect(wrapper.find('.el-empty').exists()).toBe(false)
    wrapper.unmount()
  })

  it('品种分布图使用中文品种名与真实计数', async () => {
    fetchStatsMock.mockResolvedValue(NORMAL_STATS)
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    const option = instances[0].setOption.mock.calls[0][0]
    expect(option.xAxis.data).toEqual(['比格犬', '暹罗猫', '哈瓦那犬'])
    expect(option.series[0].data).toEqual([5, 2, 1])
    wrapper.unmount()
  })

  it('每日趋势图按 UTC 日期升序展示真实计数', async () => {
    fetchStatsMock.mockResolvedValue(NORMAL_STATS)
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    const option = instances[1].setOption.mock.calls[0][0]
    expect(option.xAxis.data).toEqual(['2026-10-12', '2026-10-13'])
    expect(option.series[0].data).toEqual([3, 5])
    wrapper.unmount()
  })

  it('超过 10 个品种时标题仍为具体数量 Top 10', async () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      breed: `breed_${i}`, count: 12 - i
    }))
    fetchStatsMock.mockResolvedValue({
      ...NORMAL_STATS,
      total_predictions: 78,
      breed_distribution: many,
      daily_trend: [
        { date: '2026-10-13', count: 78 }
      ]
    })
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('品种分布（Top 10）')
    expect(wrapper.text()).toContain('合计 78 次')
    expect(instances.length).toBe(2)
    wrapper.unmount()
  })

  it('空数据：显示空状态而不是空白区域，且不初始化图表', async () => {
    fetchStatsMock.mockResolvedValue({
      success: true, total_predictions: 0,
      breed_distribution: [], daily_trend: [], avg_inference_ms: null
    })
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('.el-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无识别记录')
    expect(instances.length).toBe(0)
    wrapper.unmount()
  })

  it('加载失败：显示错误提示且不渲染图表区域', async () => {
    fetchStatsMock.mockRejectedValue(new Error('无法连接后端服务'))
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('.el-alert').exists()).toBe(true)
    expect(wrapper.text()).toContain('无法连接后端服务')
    expect(instances.length).toBe(0)
    wrapper.unmount()
  })
})

describe('StatsView 统计口径一致性', () => {
  it('分布合计与总识别次数一致（未超出 Top 10 时）', async () => {
    fetchStatsMock.mockResolvedValue(NORMAL_STATS)
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('合计 8 次')           // 5 + 2 + 1 = 8 = total_predictions
    expect(text).toContain('近 30 天合计 8 次')    // 3 + 5 = 8
    expect(text).toContain('最多 10 个品种')
    wrapper.unmount()
  })

  it('品种超出 Top 10 时分布合计小于总次数（如实反映窗口口径）', async () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      breed: `breed_${i}`, count: 12 - i
    }))
    fetchStatsMock.mockResolvedValue({
      ...NORMAL_STATS,
      total_predictions: 1000,
      breed_distribution: many,
      daily_trend: [{ date: '2026-10-13', count: 1000 }]
    })
    const { wrapper } = mountAt('/stats')
    await flushPromises()
    await flushPromises()

    // 12 个品种计数合计 78，与总数 1000 不同：标题/合计如实显示
    expect(wrapper.text()).toContain('品种分布（Top 10）')
    expect(wrapper.text()).toContain('合计 78 次')
    expect(wrapper.text()).toContain('近 30 天合计 1000 次')
    wrapper.unmount()
  })
})

describe('StatsView Back 按钮', () => {
  it('直接打开 /stats（无站内历史）时点击 Back 回退到 /predict', async () => {
    fetchStatsMock.mockResolvedValue(NORMAL_STATS)
    const { wrapper, router } = mountAt('/stats')
    await flushPromises()

    const header = wrapper.findComponent({ name: 'ElPageHeader' })
    expect(header.exists()).toBe(true)
    header.vm.$emit('back')
    await flushPromises()
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/predict')
    wrapper.unmount()
  })
})

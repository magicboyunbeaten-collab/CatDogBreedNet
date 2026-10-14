/**
 * HistoryView 组件测试：历史详情中文展示 + Back 按钮。
 *
 * 覆盖：
 *  A. 详情弹窗：predicted_breed 与 Top-K 预测均显示中文品种名
 *  B. 未映射标签回退英文原名
 *  C. 置信度、排名顺序、推理耗时保持原样
 *  D. 主列表仍展示英文标签（与数据库/API 一致）
 *  E. Back 按钮：直接打开 /history 时回退到 /predict
 *
 * 使用 mock API + 临时路由，不访问真实数据库与后端。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createWebHistory } from 'vue-router'

const { fetchHistoryMock, fetchHistoryDetailMock, deleteHistoryMock } =
  vi.hoisted(() => ({
    fetchHistoryMock: vi.fn(),
    fetchHistoryDetailMock: vi.fn(),
    deleteHistoryMock: vi.fn()
  }))

vi.mock('../src/api/history', () => ({
  fetchHistory: fetchHistoryMock,
  fetchHistoryDetail: fetchHistoryDetailMock,
  deleteHistory: deleteHistoryMock
}))

const HistoryView = (await import('../src/views/HistoryView.vue')).default

const ROUTES = [
  { path: '/', redirect: '/predict' },
  { path: '/predict', name: 'predict', component: { template: '<div>predict</div>' } },
  { path: '/history', name: 'history', component: { template: '<div>history</div>' } },
  { path: '/stats', name: 'stats', component: { template: '<div>stats</div>' } }
]

function mountAt(path) {
  window.history.replaceState(null, '', path)
  const router = createRouter({ history: createWebHistory(), routes: ROUTES })
  const wrapper = mount(HistoryView, {
    global: { plugins: [ElementPlus, router] }
  })
  return { wrapper, router }
}

const HISTORY_PAGE = {
  items: [{
    id: 7,
    image_filename: 'abc123.jpg',
    predicted_breed: 'beagle',
    confidence: 0.9123,
    inference_ms: 12.34,
    created_at: '2026-10-14T09:00:00Z'
  }],
  total: 1
}

const HISTORY_DETAIL = {
  item: {
    id: 7,
    image_filename: 'abc123.jpg',
    predicted_breed: 'beagle',
    confidence: 0.9123,
    inference_ms: 12.34,
    created_at: '2026-10-14T09:00:00Z',
    predictions: [
      { breed: 'beagle', confidence: 0.9123 },
      { breed: 'Siamese', confidence: 0.0512 },
      { breed: 'havanese', confidence: 0.02 }
    ]
  }
}

afterEach(() => {
  fetchHistoryMock.mockReset()
  fetchHistoryDetailMock.mockReset()
  deleteHistoryMock.mockReset()
  vi.restoreAllMocks()
})

function dialogBody(wrapper) {
  // 本测试环境中 ElDialog 渲染在 wrapper 内（未 teleport 到 body）
  return wrapper.find('.el-dialog__body')
}

describe('HistoryView 详情中文展示', () => {
  it('打开详情：预测品种与 Top-K 均显示中文名', async () => {
    fetchHistoryMock.mockResolvedValue(HISTORY_PAGE)
    fetchHistoryDetailMock.mockResolvedValue(HISTORY_DETAIL)
    const { wrapper } = mountAt('/history')
    await flushPromises()
    await flushPromises()

    // 主列表保持英文标签（与数据库/API 一致）
    expect(wrapper.text()).toContain('beagle')

    const detailButton = wrapper.findAll('button').find((b) => b.text() === '详情')
    expect(detailButton).toBeTruthy()
    await detailButton.trigger('click')
    await flushPromises()
    await flushPromises()

    const text = dialogBody(wrapper).text()
    // 预测品种中文
    expect(text).toContain('比格犬')
    // Top-K 中文（含排名顺序）
    expect(text).toContain('1. 比格犬')
    expect(text).toContain('2. 暹罗猫')
    expect(text).toContain('3. 哈瓦那犬')
    wrapper.unmount()
  })

  it('未映射标签回退英文原名', async () => {
    fetchHistoryMock.mockResolvedValue(HISTORY_PAGE)
    fetchHistoryDetailMock.mockResolvedValue({
      item: {
        ...HISTORY_DETAIL.item,
        predictions: [
          { breed: 'beagle', confidence: 0.9123 },
          { breed: 'border_collie', confidence: 0.03 }
        ]
      }
    })
    const { wrapper } = mountAt('/history')
    await flushPromises()
    await flushPromises()

    const detailButton = wrapper.findAll('button').find((b) => b.text() === '详情')
    await detailButton.trigger('click')
    await flushPromises()
    await flushPromises()

    const text = dialogBody(wrapper).text()
    expect(text).toContain('1. 比格犬')
    expect(text).toContain('2. border_collie') // 未映射 → 英文原名
    wrapper.unmount()
  })

  it('置信度、排名顺序与推理耗时保持原样', async () => {
    fetchHistoryMock.mockResolvedValue(HISTORY_PAGE)
    fetchHistoryDetailMock.mockResolvedValue(HISTORY_DETAIL)
    const { wrapper } = mountAt('/history')
    await flushPromises()
    await flushPromises()

    const detailButton = wrapper.findAll('button').find((b) => b.text() === '详情')
    await detailButton.trigger('click')
    await flushPromises()
    await flushPromises()

    const text = dialogBody(wrapper).text()
    expect(text).toContain('91.23%')          // 置信度原值
    expect(text).toContain('12.3 ms')         // 推理耗时原值
    // Top-3 排名顺序
    expect(text).toContain('Top-3 预测')
    expect(text.indexOf('1. 比格犬')).toBeLessThan(text.indexOf('2. 暹罗猫'))
    expect(text.indexOf('2. 暹罗猫')).toBeLessThan(text.indexOf('3. 哈瓦那犬'))
    wrapper.unmount()
  })
})

describe('HistoryView Back 按钮', () => {
  it('直接打开 /history（无站内历史）时点击 Back 回退到 /predict', async () => {
    fetchHistoryMock.mockResolvedValue(HISTORY_PAGE)
    const { wrapper, router } = mountAt('/history')
    await flushPromises()
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

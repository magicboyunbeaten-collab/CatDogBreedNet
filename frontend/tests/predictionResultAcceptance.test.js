/**
 * PredictionResult 候选组验收：使用**真实 API 响应结构**。
 *
 * ## 为什么是自包含 fixture（U6.4.1）
 *
 * 本文件原先在模块顶层用 `readFileSync` 读取
 * `reports/v2_1_four_breed_candidate_implementation/acceptance_api_responses.json`。
 * 该 JSON 位于**未跟踪**的 `reports/` 目录（项目惯例不入库），因此在一个干净的
 * 克隆里测试会因找不到文件而失败。
 *
 * 现在改为**内联 fixture**：下面的四段响应是那次隔离 API 验收（U5.2）真实返回值的
 * **逐字段原样复制**，数值未做任何改动（`group_score` 等保留原始 4 位小数），
 * 运行时不读取任何文件，也不再依赖 `reports/` 目录是否存在。
 *
 * ## fixture 的取舍
 *
 * 只保留"最小代表性"样本，但覆盖两个 Top-1 方向与两条不触发路径：
 *
 * | 常量 | 来源图片（validation，相对路径） | 作用 |
 * |---|---|---|
 * | `TRIGGERED_APBT` | `american_pit_bull_terrier/american_pit_bull_terrier_132.jpg` | Top-1 = APBT 的触发 |
 * | `TRIGGERED_AMSTAFF` | `american_staffordshire_terrier/n02093428_8135.jpg` | Top-1 = AmStaff 的触发 |
 * | `CONTROL_NOT_TRIGGERED` | `Abyssinian/Abyssinian_10.jpg` | Top-1 在组外 → `triggered=false` |
 * | `SWITCH_OFF` | `american_pit_bull_terrier/american_pit_bull_terrier_132.jpg` | 关闭总开关 → `candidate_group=null` |
 *
 * **这四段响应均不含 `group_id` 字段**（`group_id` 是 U6.2 才加入的）。保持原样既是
 * 对那份真实响应的忠实还原，也顺带覆盖了「U6.2 之前旧响应」的向后兼容路径——
 * 组件对缺失 `group_id` 有安全兜底。
 *
 * ## 覆盖（U5.2 四类候选组）
 *
 *  A. 触发响应：四品种渲染、组内得分标注、原始 Top-K 不变
 *  B. 组内得分之和为 100，且等于各自原始概率归一化
 *  C. 用户选择单独呈现，不覆盖模型预测（props 不被修改）
 *  D. 未触发响应：候选区不渲染
 *  E. 关闭开关响应：候选区不渲染
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const PredictionResult = (await import('../src/components/PredictionResult.vue')).default

/** Top-1 = american_pit_bull_terrier 的触发响应（原样复制自 U5.2 隔离验收）。 */
const TRIGGERED_APBT = {
  success: true,
  record_id: 1,
  predictions: [
    { breed: 'american_pit_bull_terrier', confidence: 0.467221 },
    { breed: 'american_staffordshire_terrier', confidence: 0.390605 },
    { breed: 'toy_terrier', confidence: 0.081247 },
  ],
  candidate_group: {
    triggered: true,
    threshold_version: 'val-2026-10-19-four-breed-b1',
    top1_breed: 'american_pit_bull_terrier',
    top1_confidence: 0.467221,
    candidates: [
      {
        breed: 'american_pit_bull_terrier',
        breed_zh: '美国比特斗牛梗',
        original_confidence: 0.467221,
        group_score: 54.4621,
      },
      {
        breed: 'american_staffordshire_terrier',
        breed_zh: '美国斯塔福郡梗',
        original_confidence: 0.390605,
        group_score: 45.5313,
      },
      {
        breed: 'staffordshire_bull_terrier',
        breed_zh: '斯塔福郡斗牛梗',
        original_confidence: 0.000039,
        group_score: 0.0045,
      },
      {
        breed: 'american_bulldog',
        breed_zh: '美国斗牛犬',
        original_confidence: 0.000018,
        group_score: 0.0021,
      },
    ],
    available_candidates: [
      'american_pit_bull_terrier',
      'american_staffordshire_terrier',
      'staffordshire_bull_terrier',
      'american_bulldog',
    ],
    group_mass: 0.857883,
    group_margin: 0.076616,
    reason: 'top-1 在候选组内、组内总概率 0.8579 ≥ 0.30 且组内分差 0.0766 ≤ 0.40',
  },
  elapsed_ms: 242.733,
  inference_ms: 210.56,
  preprocess_ms: 4.203,
  top_k: 3,
  num_classes: 136,
  note: 'confidence is a softmax score over the trained class set, not a true probability',
}

/** Top-1 = american_staffordshire_terrier 的触发响应（原样复制自 U5.2 隔离验收）。 */
const TRIGGERED_AMSTAFF = {
  success: true,
  record_id: 4,
  predictions: [
    { breed: 'american_staffordshire_terrier', confidence: 0.46589 },
    { breed: 'weimaraner', confidence: 0.371589 },
    { breed: 'american_pit_bull_terrier', confidence: 0.101559 },
  ],
  candidate_group: {
    triggered: true,
    threshold_version: 'val-2026-10-19-four-breed-b1',
    top1_breed: 'american_staffordshire_terrier',
    top1_confidence: 0.46589,
    candidates: [
      {
        breed: 'american_staffordshire_terrier',
        breed_zh: '美国斯塔福郡梗',
        original_confidence: 0.46589,
        group_score: 81.8986,
      },
      {
        breed: 'american_pit_bull_terrier',
        breed_zh: '美国比特斗牛梗',
        original_confidence: 0.101559,
        group_score: 17.853,
      },
      {
        breed: 'american_bulldog',
        breed_zh: '美国斗牛犬',
        original_confidence: 0.001404,
        group_score: 0.2468,
      },
      {
        breed: 'staffordshire_bull_terrier',
        breed_zh: '斯塔福郡斗牛梗',
        original_confidence: 0.000009,
        group_score: 0.0016,
      },
    ],
    available_candidates: [
      'american_pit_bull_terrier',
      'american_staffordshire_terrier',
      'staffordshire_bull_terrier',
      'american_bulldog',
    ],
    group_mass: 0.568862,
    group_margin: 0.364331,
    reason: 'top-1 在候选组内、组内总概率 0.5689 ≥ 0.30 且组内分差 0.3643 ≤ 0.40',
  },
  elapsed_ms: 25.372,
  inference_ms: 2.431,
  preprocess_ms: 1.265,
  top_k: 3,
  num_classes: 136,
  note: 'confidence is a softmax score over the trained class set, not a true probability',
}

/** Top-1 在候选组外（Abyssinian）→ triggered=false 的响应。 */
const CONTROL_NOT_TRIGGERED = {
  success: true,
  record_id: 1,
  predictions: [
    { breed: 'Abyssinian', confidence: 0.691075 },
    { breed: 'Sphynx', confidence: 0.090271 },
    { breed: 'miniature_schnauzer', confidence: 0.055825 },
  ],
  candidate_group: {
    triggered: false,
    threshold_version: 'val-2026-10-19-four-breed-b1',
    top1_breed: 'Abyssinian',
    top1_confidence: 0.691075,
    candidates: [
      {
        breed: 'american_bulldog',
        breed_zh: '美国斗牛犬',
        original_confidence: 0.000407,
        group_score: 96.6747,
      },
      {
        breed: 'staffordshire_bull_terrier',
        breed_zh: '斯塔福郡斗牛梗',
        original_confidence: 0.000008,
        group_score: 1.9002,
      },
      {
        breed: 'american_staffordshire_terrier',
        breed_zh: '美国斯塔福郡梗',
        original_confidence: 0.000005,
        group_score: 1.1876,
      },
      {
        breed: 'american_pit_bull_terrier',
        breed_zh: '美国比特斗牛梗',
        original_confidence: 0.000001,
        group_score: 0.2375,
      },
    ],
    available_candidates: [
      'american_pit_bull_terrier',
      'american_staffordshire_terrier',
      'staffordshire_bull_terrier',
      'american_bulldog',
    ],
    group_mass: 0.000421,
    group_margin: 0.000399,
    reason: 'top-1 不在候选组内',
  },
  elapsed_ms: 31.118,
  inference_ms: 6.855,
  preprocess_ms: 3.864,
  top_k: 3,
  num_classes: 136,
  note: 'confidence is a softmax score over the trained class set, not a true probability',
}

/** 关闭 CATDOG_CANDIDATE_GROUP_ENABLED 后的响应：候选组为 null。 */
const SWITCH_OFF = {
  success: true,
  record_id: 1,
  predictions: [
    { breed: 'american_pit_bull_terrier', confidence: 0.467221 },
    { breed: 'american_staffordshire_terrier', confidence: 0.390605 },
    { breed: 'toy_terrier', confidence: 0.081247 },
  ],
  candidate_group: null,
  elapsed_ms: 27.656,
  inference_ms: 7.244,
  preprocess_ms: 3.13,
  top_k: 3,
  num_classes: 136,
  note: 'confidence is a softmax score over the trained class set, not a true probability',
}

// 与原先 `evidence.triggered` / `.controls` / `.switch_off` 同形的本地样本集合，
// 这样 8 个用例的断言体可以保持原样。
const triggered = [
  { image: 'val/american_pit_bull_terrier/american_pit_bull_terrier_132.jpg', response: TRIGGERED_APBT },
  { image: 'val/american_staffordshire_terrier/n02093428_8135.jpg', response: TRIGGERED_AMSTAFF },
]
const controls = [
  { image: 'val/Abyssinian/Abyssinian_10.jpg', response: CONTROL_NOT_TRIGGERED },
]
const switchOff = [
  { image: 'val/american_pit_bull_terrier/american_pit_bull_terrier_132.jpg', response: SWITCH_OFF },
]

function mountResult(result) {
  return mount(PredictionResult, {
    props: { result },
    global: { plugins: [ElementPlus] },
  })
}

describe('候选组验收（真实 API 响应结构，U5.2 四类）', () => {
  it('A. 每个触发响应都渲染四个候选品种', () => {
    expect(triggered.length).toBeGreaterThan(0)
    for (const item of triggered) {
      const group = item.response.candidate_group
      expect(group.triggered).toBe(true)
      expect(group.candidates.length).toBe(4)
      const wrapper = mountResult(item.response)
      const text = wrapper.text()
      for (const candidate of group.candidates) {
        expect(text).toContain(candidate.breed_zh)
      }
      wrapper.unmount()
    }
  })

  it('B. 组内得分之和为 100 且标注为"候选组内相对得分"', () => {
    for (const item of triggered) {
      const group = item.response.candidate_group
      const total = group.candidates.reduce(
        (sum, c) => sum + c.group_score, 0)
      expect(total).toBeCloseTo(100, 2)
      const wrapper = mountResult(item.response)
      expect(wrapper.text()).toContain('候选组内相对得分')
      expect(wrapper.text()).toContain('不是')
      wrapper.unmount()
    }
  })

  it('C. 组内得分严格等于各自原始概率归一化', () => {
    for (const item of triggered) {
      const group = item.response.candidate_group
      for (const candidate of group.candidates) {
        const expected = candidate.original_confidence / group.group_mass * 100
        expect(candidate.group_score).toBeCloseTo(expected, 2)
      }
    }
  })

  it('D. 原始 Top-K 与模型首选不被替换', () => {
    for (const item of triggered) {
      const group = item.response.candidate_group
      const wrapper = mountResult(item.response)
      const text = wrapper.text()
      expect(text).toContain('Top-1')
      expect(text).toContain(
        `${(item.response.predictions[0].confidence * 100).toFixed(2)}%`)
      expect(group.top1_breed).toBe(item.response.predictions[0].breed)
      expect(group.top1_confidence)
        .toBeCloseTo(item.response.predictions[0].confidence, 9)
      wrapper.unmount()
    }
  })

  it('E. 用户选择单独呈现且不覆盖模型预测', async () => {
    const item = triggered[0]
    const group = item.response.candidate_group
    const wrapper = mountResult(item.response)

    expect(wrapper.text()).toContain('你选择的品种')
    expect(wrapper.text()).toContain('模型首选仍为')

    const radios = wrapper.findAllComponents({ name: 'ElRadio' })
    expect(radios.length).toBe(4)
    // 选一个非首选的候选
    const other = group.candidates.find(
      (c) => c.breed !== group.top1_breed)
    await radios[1].vm.$emit('change', other.breed)
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain(other.breed_zh)
    expect(text).toContain('模型首选仍为')
    expect(text).toContain('未被替换')

    // props 完全未被修改
    expect(wrapper.props().result.predictions[0].breed)
      .toBe(group.top1_breed)
    expect(wrapper.props().result.candidate_group.top1_breed)
      .toBe(group.top1_breed)
    wrapper.unmount()
  })

  it('F. 未触发响应不渲染候选区', () => {
    expect(controls.length).toBeGreaterThan(0)
    for (const item of controls) {
      const wrapper = mountResult(item.response)
      expect(wrapper.find('.candidate-block').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('外观相近的候选品种')
      wrapper.unmount()
    }
  })

  it('G. 关闭开关的响应不渲染候选区', () => {
    expect(switchOff.length).toBeGreaterThan(0)
    for (const item of switchOff) {
      expect(item.response.candidate_group ?? null).toBeNull()
      const wrapper = mountResult(item.response)
      expect(wrapper.find('.candidate-block').exists()).toBe(false)
      wrapper.unmount()
    }
  })

  it('H. 解释提示含"登记品种"且不暗示必有正确答案', () => {
    const wrapper = mountResult(triggered[0].response)
    const text = wrapper.text()
    expect(text).toContain('登记品种')
    expect(text).toContain('单张图片未必足以可靠区分')
    expect(text).not.toContain('其中必有一个')
    expect(text).not.toContain('一定是')
    wrapper.unmount()
  })
})

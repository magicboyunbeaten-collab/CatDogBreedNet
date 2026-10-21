/**
 * PredictionResult 组件测试：相近犬种候选组（U5.2 四类）。
 *
 * 覆盖：
 *  A. 未触发候选组时，页面与改动前一致（不渲染候选区）
 *  B. 候选组字段缺失（功能关闭 / V1.1）时不渲染候选区
 *  C. 触发时展示四个候选及中文名
 *  D. 组内相对得分之和为 100，且标注为"候选组内相对得分"（非整体置信度）
 *  E. 模型预测保持原样：原始 Top-K 与 top-1 不被替换
 *  F. 用户选择单独呈现，不覆盖模型预测
 *  G. 未触发时用户选择区不出现
 *  H. 文案说明不代表登记品种、且不暗示四类中必有正确答案
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const PredictionResult = (await import('../src/components/PredictionResult.vue')).default

const APBT = 'american_pit_bull_terrier'
const AMSTAFF = 'american_staffordshire_terrier'
const SBT = 'staffordshire_bull_terrier'
const AMBULL = 'american_bulldog'

/** 构造一次识别结果；candidateGroup 传 null 表示功能关闭/未触发。 */
function makeResult(candidateGroup) {
  return {
    record_id: 42,
    predictions: [
      { breed: APBT, confidence: 0.42 },
      { breed: AMSTAFF, confidence: 0.3 },
      { breed: AMBULL, confidence: 0.26 },
    ],
    candidate_group: candidateGroup,
    elapsed_ms: 12.3,
    inference_ms: 8.1,
    preprocess_ms: 4.2,
    top_k: 3,
    num_classes: 136,
    note: 'confidence is a softmax score over the trained class set',
  }
}

const TRIGGERED_GROUP = {
  triggered: true,
  threshold_version: 'val-2026-10-19-four-breed-b1',
  top1_breed: APBT,
  top1_confidence: 0.42,
  // group_mass = 0.42 + 0.30 + 0.26 + 0.05 = 1.03
  // 组内得分 = 各自 original_confidence / group_mass * 100
  candidates: [
    { breed: APBT, breed_zh: '美国比特斗牛梗', original_confidence: 0.42, group_score: 40.7767 },
    { breed: AMSTAFF, breed_zh: '美国斯塔福郡梗', original_confidence: 0.3, group_score: 29.1262 },
    { breed: AMBULL, breed_zh: '美国斗牛犬', original_confidence: 0.26, group_score: 25.2427 },
    { breed: SBT, breed_zh: '斯塔福郡斗牛梗', original_confidence: 0.05, group_score: 4.8544 },
  ],
  available_candidates: [APBT, AMSTAFF, SBT, AMBULL],
  group_mass: 1.03,
  group_margin: 0.12,
  reason: 'top-1 在候选组内、组内总概率 1.0300 ≥ 0.30 且组内分差 0.1200 ≤ 0.40',
}

function mountResult(result) {
  return mount(PredictionResult, {
    props: { result },
    global: { plugins: [ElementPlus] },
  })
}

describe('PredictionResult 候选组（U5.2 四类）', () => {
  it('A. 未触发时不渲染候选区', () => {
    const wrapper = mountResult(makeResult(null))
    expect(wrapper.text()).not.toContain('外观相近的候选品种')
    expect(wrapper.text()).not.toContain('你选择的品种')
    wrapper.unmount()
  })

  it('B. triggered=false 时同样不渲染候选区', () => {
    const wrapper = mountResult(
      makeResult({ ...TRIGGERED_GROUP, triggered: false }))
    expect(wrapper.text()).not.toContain('外观相近的候选品种')
    wrapper.unmount()
  })

  it('C. 触发时展示四个候选及中文名', () => {
    const wrapper = mountResult(makeResult(TRIGGERED_GROUP))
    const text = wrapper.text()
    expect(text).toContain('外观相近的候选品种')
    expect(text).toContain('美国比特斗牛梗')
    expect(text).toContain('美国斯塔福郡梗')
    expect(text).toContain('斯塔福郡斗牛梗')
    expect(text).toContain('美国斗牛犬')
    wrapper.unmount()
  })

  it('D. 组内相对得分之和为 100，并标注为"候选组内相对得分"', () => {
    const wrapper = mountResult(makeResult(TRIGGERED_GROUP))
    const total = TRIGGERED_GROUP.candidates.reduce(
      (sum, item) => sum + item.group_score, 0)
    expect(total).toBeCloseTo(100, 2)
    const text = wrapper.text()
    expect(text).toContain('候选组内相对得分')
    expect(text).toContain('不是')
    // 原始 Softmax 分数仍需可见，供调试追踪
    expect(text).toContain('原始分')
    wrapper.unmount()
  })

  it('E. 模型预测保持原样，不被候选区替换', () => {
    const wrapper = mountResult(makeResult(TRIGGERED_GROUP))
    const text = wrapper.text()
    // 原始 Top-1 仍是 APBT，且原始 softmax 百分比保留
    expect(text).toContain('42.00%')
    // Top-2 / Top-3 也保持渲染
    expect(text).toContain('Top-2')
    expect(text).toContain('Top-3')
    wrapper.unmount()
  })

  it('F. 用户选择单独呈现，且不覆盖模型预测', async () => {
    const wrapper = mountResult(makeResult(TRIGGERED_GROUP))
    // 默认选中模型首选
    expect(wrapper.text()).toContain('你选择的品种')
    expect(wrapper.text()).toContain('模型首选仍为')

    const radios = wrapper.findAllComponents({ name: 'ElRadio' })
    expect(radios.length).toBe(4)
    // 选择第二个候选（AmStaff）
    await radios[1].vm.$emit('change', AMSTAFF)
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('美国斯塔福郡梗')
    // 模型预测区块未被替换
    expect(text).toContain('模型首选仍为')
    expect(text).toContain('未被替换')
    // props 未被修改
    expect(wrapper.props().result.predictions[0].breed).toBe(APBT)
    expect(wrapper.props().result.candidate_group.top1_breed).toBe(APBT)
    wrapper.unmount()
  })

  it('G. 未触发时用户选择区不出现', () => {
    const wrapper = mountResult(makeResult(null))
    expect(wrapper.find('.user-choice').exists()).toBe(false)
    expect(wrapper.find('.candidate-block').exists()).toBe(false)
    wrapper.unmount()
  })

  it('H. 解释提示说明不代表登记品种，且不暗示必有正确答案', () => {
    const wrapper = mountResult(makeResult(TRIGGERED_GROUP))
    const text = wrapper.text()
    expect(text).toContain('登记品种')
    expect(text).toContain('单张图片未必足以可靠区分')
    // 不得暗示四类中必然存在正确答案
    expect(text).not.toContain('其中必有一个')
    expect(text).not.toContain('必然')
    expect(text).not.toContain('一定是')
    wrapper.unmount()
  })
})

// ---------------------------------------------------------------------------
// U5.4：候选数量文案与同图一致性的前端回归
// ---------------------------------------------------------------------------

/** 从图例文案中解析"N 个候选"的 N（兼容阿拉伯数字与中文数字）。 */
const NUM_ZH = ['零', '一', '两', '三', '四', '五', '六', '七', '八', '九']
function parseCandidateCount(text) {
  const match = String(text || '').match(/([0-9]+|[一二两三四五六七八九])\s*个候选/)
  if (!match) return NaN
  const raw = match[1]
  return /^[0-9]+$/.test(raw) ? Number(raw) : NUM_ZH.indexOf(raw)
}

/**
 * 构造一个自洽的候选组：group_score 由原始概率归一化得出，
 * 并把四舍五入漂移补到最大项（与后端实现一致），保证和为 100。
 */
function buildGroup(entries) {
  const mass = entries.reduce((sum, item) => sum + item.prob, 0)
  const scores = entries.map((item) => Math.round((item.prob / mass) * 1e4) / 1e4)
  const drift = Math.round((100 - scores.reduce((a, b) => a + b, 0)) * 1e4) / 1e4
  if (drift && scores.length > 1) {
    scores[0] = Math.round((scores[0] + drift) * 1e4) / 1e4
  }
  return {
    triggered: true,
    threshold_version: 'val-2026-10-19-four-breed-b1',
    top1_breed: entries[0].breed,
    top1_confidence: entries[0].prob,
    candidates: entries.map((item, index) => ({
      breed: item.breed,
      breed_zh: item.zh,
      original_confidence: item.prob,
      group_score: scores[index],
    })),
    available_candidates: entries.map((item) => item.breed),
    group_mass: mass,
    group_margin: entries[0].prob - entries[1].prob,
    reason: 'test fixture',
  }
}

const ENTRY = {
  [APBT]: { breed: APBT, zh: '美国比特斗牛梗' },
  [AMSTAFF]: { breed: AMSTAFF, zh: '美国斯塔福郡梗' },
  [SBT]: { breed: SBT, zh: '斯塔福郡斗牛梗' },
  [AMBULL]: { breed: AMBULL, zh: '美国斗牛犬' },
}

const THREE_CANDIDATE_GROUP = buildGroup([
  { ...ENTRY[AMSTAFF], prob: 0.4 },
  { ...ENTRY[SBT], prob: 0.3 },
  { ...ENTRY[AMBULL], prob: 0.2 },
])

const TWO_CANDIDATE_GROUP = buildGroup([
  { ...ENTRY[AMSTAFF], prob: 0.45 },
  { ...ENTRY[AMBULL], prob: 0.25 },
])

describe('PredictionResult 候选数量文案（U5.4 回归）', () => {
  it('I. 四个候选时图例文案显示 4 个候选', () => {
    const wrapper = mountResult(makeResult(TRIGGERED_GROUP))
    const legend = wrapper.find('.candidate-legend').text()
    expect(parseCandidateCount(legend)).toBe(4)
    // 文案必须仍然声明"非整体置信度"的含义，不得因动态数量而丢失
    expect(legend).toContain('候选组内相对得分')
    expect(legend).toContain('不是')
    wrapper.unmount()
  })

  it('J. 三个候选时图例为 3 且候选行为 3（证明未硬编码 3 或 4）', () => {
    const wrapper = mountResult(makeResult(THREE_CANDIDATE_GROUP))
    expect(parseCandidateCount(wrapper.find('.candidate-legend').text())).toBe(3)
    expect(wrapper.findAll('.candidate-row')).toHaveLength(3)
    expect(wrapper.findAllComponents({ name: 'ElRadio' })).toHaveLength(3)
    // 三个候选的中文名都要渲染
    for (const item of THREE_CANDIDATE_GROUP.candidates) {
      expect(wrapper.text()).toContain(item.breed_zh)
    }
    wrapper.unmount()
  })

  it('K. 候选数量文案恒等于 candidates.length（2/3/4 参数化）', () => {
    const groups = [TWO_CANDIDATE_GROUP, THREE_CANDIDATE_GROUP, TRIGGERED_GROUP]
    for (const group of groups) {
      const wrapper = mountResult(makeResult(group))
      const expected = group.candidates.length
      expect(parseCandidateCount(wrapper.find('.candidate-legend').text()))
        .toBe(expected)
      expect(wrapper.findAll('.candidate-row')).toHaveLength(expected)
      // 组内得分之和应约为 100（构造的 fixture 已按后端规则补齐漂移）
      const sum = group.candidates.reduce((s, c) => s + c.group_score, 0)
      expect(sum).toBeCloseTo(100, 2)
      wrapper.unmount()
    }
  })

  it('L. candidate_group 键缺失（undefined）时不渲染候选区与用户选择区', () => {
    const wrapper = mountResult(makeResult(undefined))
    expect(wrapper.find('.candidate-block').exists()).toBe(false)
    expect(wrapper.find('.user-choice').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('外观相近的候选品种')
    expect(wrapper.text()).not.toContain('你选择的品种')
    // 原始 Top-K 仍正常渲染
    expect(wrapper.findAll('.prediction-row')).toHaveLength(3)
    wrapper.unmount()
  })

  it('M. 用户选择候选后原始 Top-1 / Top-K / 原始分数全部不变', async () => {
    const result = makeResult(TRIGGERED_GROUP)
    const predictionsBefore = JSON.parse(JSON.stringify(result.predictions))
    const wrapper = mountResult(result)

    const rowsBefore = wrapper.findAll('.prediction-row').map((row) => row.text())
    const textBefore = wrapper.text()

    // 选择第 3 个候选（SBT），与模型首选 APBT 不同
    const radios = wrapper.findAllComponents({ name: 'ElRadio' })
    await radios[2].vm.$emit('change', SBT)
    await wrapper.vm.$nextTick()

    // 1) props 中 predictions 全数组逐项未变（breed + confidence）
    expect(wrapper.props().result.predictions).toEqual(predictionsBefore)
    // 2) 原始 Top-K 每一行的渲染文本未变
    const rowsAfter = wrapper.findAll('.prediction-row').map((row) => row.text())
    expect(rowsAfter).toEqual(rowsBefore)
    // 3) 原始 Top-1 的百分比文本仍在（未被候选得分替换）
    expect(textBefore).toContain('42.00%')
    expect(wrapper.text()).toContain('42.00%')
    // 4) 用户选择确实切换到了 SBT，且模型首选仍是 APBT
    expect(wrapper.text()).toContain('斯塔福郡斗牛梗')
    expect(wrapper.text()).toContain('模型首选仍为')
    expect(wrapper.text()).toContain('未被替换')
    expect(wrapper.props().result.predictions[0].breed).toBe(APBT)
    expect(wrapper.props().result.predictions[0].confidence).toBe(0.42)
    wrapper.unmount()
  })
})

/**
 * U6.2：柯利牧羊犬 / 边境牧羊犬双候选提示的前端回归测试。
 *
 * 覆盖任务 §4.2 列出的 6 项要求：
 * 1. 两个候选中文名与数量正确；四类组仍显示四项；
 * 2. 双候选组分数合计约为 100%，并标注"候选组内相对得分"；
 * 3. 文案不暗示其中必然有正确答案；
 * 4. 用户选择后只更新"你选择的品种"，不改变模型 Top-1、Top-K 和原始分数；
 * 5. candidate_group 为 null、undefined、triggered=false 时均不显示候选区；
 * 6. 两种候选组按响应的组标识正确渲染，无三/四候选硬编码混淆。
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import PredictionResult from '../src/components/PredictionResult.vue'

const APBT = 'american_pit_bull_terrier'
const AMSTAFF = 'american_staffordshire_terrier'
const SBT = 'staffordshire_bull_terrier'
const AMBULL = 'american_bulldog'
const COLLIE = 'collie'
const BORDER_COLLIE = 'border_collie'

const FOUR_BREED_VERSION = 'val-2026-10-19-four-breed-b1'
const COLLIE_PAIR_VERSION = 'val-2026-10-21-collie-pair-v1'

/** 四类 bully 组（既有策略，用于"仍显示四项"的回归对照）。 */
const BULLY_GROUP = {
  group_id: 'four-breed-bully',
  triggered: true,
  threshold_version: FOUR_BREED_VERSION,
  top1_breed: APBT,
  top1_confidence: 0.42,
  candidates: [
    { breed: APBT, breed_zh: '美国比特斗牛梗', original_confidence: 0.42, group_score: 40.7767 },
    { breed: AMSTAFF, breed_zh: '美国斯塔福郡梗', original_confidence: 0.3, group_score: 29.1262 },
    { breed: AMBULL, breed_zh: '美国斗牛犬', original_confidence: 0.26, group_score: 25.2427 },
    { breed: SBT, breed_zh: '斯塔福郡斗牛梗', original_confidence: 0.05, group_score: 4.8544 },
  ],
  available_candidates: [APBT, AMSTAFF, SBT, AMBULL],
  group_mass: 1.03,
  group_margin: 0.12,
  reason: 'test',
}

/** 双候选组：分数严格按 0.6032 / 0.3955 归一化，**不硬编码 50/50**。 */
const PAIR_GROUP = {
  group_id: 'collie-pair',
  triggered: true,
  threshold_version: COLLIE_PAIR_VERSION,
  top1_breed: COLLIE,
  top1_confidence: 0.6032,
  candidates: [
    { breed: COLLIE, breed_zh: '柯利牧羊犬', original_confidence: 0.6032, group_score: 60.3985 },
    { breed: BORDER_COLLIE, breed_zh: '边境牧羊犬', original_confidence: 0.3955, group_score: 39.6015 },
  ],
  available_candidates: [COLLIE, BORDER_COLLIE],
  group_mass: 0.9987,
  group_margin: 0.2077,
  reason: 'test',
}

function makeResult(candidateGroup, top1 = COLLIE, top1Confidence = 0.6032) {
  return {
    record_id: 42,
    predictions: [
      { breed: top1, confidence: top1Confidence },
      { breed: BORDER_COLLIE, confidence: 0.3955 },
      { breed: 'beagle', confidence: 0.001 },
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

function mountResult(result) {
  return mount(PredictionResult, {
    props: { result },
    global: { plugins: [ElementPlus] },
  })
}

/** 从图例文案中解析"N 个候选"的 N（兼容阿拉伯数字与中文数字）。 */
const NUM_ZH = ['零', '一', '两', '三', '四', '五', '六', '七', '八', '九']
function parseCandidateCount(text) {
  const match = String(text || '').match(/([0-9]+|[一二两三四五六七八九])\s*个候选/)
  if (!match) return NaN
  const raw = match[1]
  return /^[0-9]+$/.test(raw) ? Number(raw) : NUM_ZH.indexOf(raw)
}

describe('PredictionResult 柯利/边境牧羊犬双候选（U6.2）', () => {
  it('1. 两个候选中文名与数量正确；四类组仍显示四项', () => {
    const wrapper = mountResult(makeResult(PAIR_GROUP))
    const rows = wrapper.findAll('.candidate-row')
    expect(rows).toHaveLength(2)
    expect(wrapper.text()).toContain('柯利牧羊犬')
    expect(wrapper.text()).toContain('边境牧羊犬')
    // 两个中文名互不混淆，且不得出现其它品种名
    expect(wrapper.text()).not.toContain('美国比特斗牛梗')
    // 组标识正确渲染
    expect(wrapper.find('.candidate-group-id').text()).toBe('collie-pair')
    expect(wrapper.find('.candidate-group-id').attributes('data-group-id'))
      .toBe('collie-pair')
    // 两类组副标题如实说明是这两个牧羊犬难以区分
    expect(wrapper.text()).toContain('模型对柯利牧羊犬与边境牧羊犬难以明确区分')

    // 四类组回归：仍显示四项，且组标识不同
    const bully = mountResult(makeResult(BULLY_GROUP, APBT, 0.42))
    expect(bully.findAll('.candidate-row')).toHaveLength(4)
    expect(bully.find('.candidate-group-id').text()).toBe('four-breed-bully')
    expect(bully.text()).toContain('模型在这几个品种间难以明确区分')
    wrapper.unmount()
    bully.unmount()
  })

  it('2. 双候选组分数合计约为 100%，并标注"候选组内相对得分"', () => {
    const wrapper = mountResult(makeResult(PAIR_GROUP))
    const scores = PAIR_GROUP.candidates.map((c) => c.group_score)
    expect(scores.reduce((a, b) => a + b, 0)).toBeCloseTo(100, 2)
    // 不硬编码 50/50：必须如实反映 60.4 / 39.6
    expect(scores[0]).toBeCloseTo(60.3985, 3)
    expect(scores[1]).toBeCloseTo(39.6015, 3)
    const legend = wrapper.find('.candidate-legend').text()
    expect(legend).toContain('候选组内相对得分')
    expect(legend).toContain(COLLIE_PAIR_VERSION)
    expect(legend).toContain('不是')
    expect(legend).toContain('整体识别置信度')
    expect(parseCandidateCount(legend)).toBe(2)
    wrapper.unmount()
  })

  it('3. 文案不暗示其中必然有正确答案', () => {
    const wrapper = mountResult(makeResult(PAIR_GROUP))
    const text = wrapper.text()
    expect(text).not.toContain('其中必有一个')
    expect(text).not.toContain('必然')
    expect(text).not.toContain('一定是')
    expect(text).not.toContain('正确品种是')
    // 必须声明不保证候选中一定包含正确品种
    expect(text).toContain('不保证候选中一定包含正确品种')
    wrapper.unmount()
  })

  it('4. 用户选择后只更新"你选择的品种"，不改模型 Top-1/Top-K/原始分数', async () => {
    const result = makeResult(PAIR_GROUP)
    const predictionsBefore = JSON.parse(JSON.stringify(result.predictions))
    const wrapper = mountResult(result)

    const rowsBefore = wrapper.findAll('.prediction-row').map((r) => r.text())
    const textBefore = wrapper.text()

    // 选择第 2 个候选（边境牧羊犬），与模型首选柯利牧羊犬不同
    const radios = wrapper.findAllComponents({ name: 'ElRadio' })
    await radios[1].vm.$emit('change', BORDER_COLLIE)
    await wrapper.vm.$nextTick()

    // 1) props 中 predictions 全数组逐项未变
    expect(wrapper.props().result.predictions).toEqual(predictionsBefore)
    // 2) 原始 Top-K 每一行的渲染文本未变
    expect(wrapper.findAll('.prediction-row').map((r) => r.text()))
      .toEqual(rowsBefore)
    // 3) 原始 Top-1 分数文本仍在（60.32%），未被候选得分替换
    expect(textBefore).toContain('60.32%')
    expect(wrapper.text()).toContain('60.32%')
    // 4) 用户选择确实切换，且模型首选仍为柯利牧羊犬
    expect(wrapper.text()).toContain('边境牧羊犬')
    expect(wrapper.text()).toContain('模型首选仍为')
    expect(wrapper.text()).toContain('未被替换')
    expect(wrapper.props().result.predictions[0].breed).toBe(COLLIE)
    expect(wrapper.props().result.predictions[0].confidence).toBe(0.6032)
    wrapper.unmount()
  })

  it('5. candidate_group 为 null / undefined / triggered=false 均不显示候选区', () => {
    for (const group of [null, undefined, { ...PAIR_GROUP, triggered: false }]) {
      const wrapper = mountResult(makeResult(group))
      expect(wrapper.find('.candidate-block').exists()).toBe(false)
      expect(wrapper.find('.user-choice').exists()).toBe(false)
      expect(wrapper.find('.candidate-group-id').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('外观相近的候选品种')
      expect(wrapper.text()).not.toContain('你选择的品种')
      // 原始 Top-K 仍正常渲染
      expect(wrapper.findAll('.prediction-row')).toHaveLength(3)
      wrapper.unmount()
    }
  })

  it('6. 两种候选组按组标识正确渲染，无三/四候选硬编码混淆', () => {
    // 双候选：图例解析出 2，副标题指向牧羊犬
    const pair = mountResult(makeResult(PAIR_GROUP))
    expect(parseCandidateCount(pair.find('.candidate-legend').text())).toBe(2)
    expect(pair.findAll('.candidate-row')).toHaveLength(2)
    expect(pair.find('.candidate-group-id').attributes('data-group-id'))
      .toBe('collie-pair')

    // 四类：图例解析出 4，副标题指向通用表述
    const bully = mountResult(makeResult(BULLY_GROUP, APBT, 0.42))
    expect(parseCandidateCount(bully.find('.candidate-legend').text())).toBe(4)
    expect(bully.findAll('.candidate-row')).toHaveLength(4)
    expect(bully.find('.candidate-group-id').attributes('data-group-id'))
      .toBe('four-breed-bully')

    // 两者的阈值版本不得混用
    expect(pair.find('.candidate-legend').text())
      .toContain(COLLIE_PAIR_VERSION)
    expect(pair.find('.candidate-legend').text())
      .not.toContain(FOUR_BREED_VERSION)
    expect(bully.find('.candidate-legend').text())
      .toContain(FOUR_BREED_VERSION)
    expect(bully.find('.candidate-legend').text())
      .not.toContain(COLLIE_PAIR_VERSION)

    pair.unmount()
    bully.unmount()
  })
})

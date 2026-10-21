/**
 * Unit tests for the Chinese breed-name mapping.
 *
 * U5.5：系统默认模型已切换为 V2.1（136 类），因此
 *  - 主映射必须覆盖 **V2.1 的 136 个 canonical label**（读取真实
 *    `artifacts/v2_1_136classes_seed42/class_names.json`，防止映射静默漂移）；
 *  - 同时保留 **V1.1 旧 37 类** 的兼容性断言（名称保持不变、仍可解析），
 *    确保历史记录（旧 37 类标签）在新版本下依然显示原中文名。
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  BREED_MAPPING_SIZE,
  CANDIDATE_GROUP,
  getBreedDisplayName,
  getBreedMapping,
} from '../src/utils/breedNames'

const here = dirname(fileURLToPath(import.meta.url))

/** V2.1（136 类）—— 当前默认模型的类别空间 */
const v21ClassNames = JSON.parse(
  readFileSync(resolve(here, '../../artifacts/v2_1_136classes_seed42/class_names.json'),
    'utf-8'))

/** V1.1（37 类）—— 历史记录兼容性参照 */
const v11ClassNames = JSON.parse(
  readFileSync(resolve(here, '../../artifacts/class_names.json'), 'utf-8'))

describe('breedNames mapping（V2.1 136 类）', () => {
  it('covers every V2.1 canonical label with a non-empty Chinese name', () => {
    const labelCount = v21ClassNames.length
    expect(labelCount).toBe(136)
    expect(BREED_MAPPING_SIZE).toBe(labelCount)

    const mapping = getBreedMapping()
    const missing = []
    for (const name of v21ClassNames) {
      if (!Object.prototype.hasOwnProperty.call(mapping, name)) missing.push(name)
      else if (!/\S/.test(mapping[name])) missing.push(name)
    }
    expect(missing).toEqual([])
  })

  it('has no duplicate keys and no duplicate Chinese names', () => {
    const mapping = getBreedMapping()
    const keys = Object.keys(mapping)
    expect(new Set(keys).size).toBe(keys.length)

    const values = Object.values(mapping)
    expect(new Set(values).size).toBe(values.length)
  })

  it('never renders an English underscore label as the main name', () => {
    // 映射中的每个键都必须渲染成不含下划线的中文名
    for (const label of v21ClassNames) {
      const display = getBreedDisplayName(label)
      expect(display).not.toBe(label)
      expect(display).not.toContain('_')
    }
  })

  it('keeps the original 37 V1.1 labels compatible (names unchanged)', () => {
    const mapping = getBreedMapping()
    // V1.1 的 37 类必须全部仍在新映射中，且中文名与原值一致
    for (const label of v11ClassNames) {
      expect(Object.prototype.hasOwnProperty.call(mapping, label)).toBe(true)
      expect(getBreedDisplayName(label)).toMatch(/\S/)
      expect(getBreedDisplayName(label)).not.toBe(label)
    }
    // 抽查几个 V1.1 时期的代表性名称，确保含义未被改写
    expect(getBreedDisplayName('Siamese')).toBe('暹罗猫')
    expect(getBreedDisplayName('Bengal')).toBe('孟加拉猫')
    expect(getBreedDisplayName('Persian')).toBe('波斯猫')
    expect(getBreedDisplayName('beagle')).toBe('比格犬')
    expect(getBreedDisplayName('pug')).toBe('巴哥犬')
    expect(getBreedDisplayName('samoyed')).toBe('萨摩耶犬')
  })

  it('keeps border collie / collie / border terrier distinct', () => {
    // 三个易混类别必须各自独立、名称互不混淆，且英文 canonical label 未被改动
    const borderCollie = getBreedDisplayName('border_collie')
    const collie = getBreedDisplayName('collie')
    const borderTerrier = getBreedDisplayName('border_terrier')

    expect(borderCollie).toBe('边境牧羊犬')
    expect(collie).toBe('柯利牧羊犬')
    expect(borderTerrier).toBe('边境梗')

    const distinct = new Set([borderCollie, collie, borderTerrier])
    expect(distinct.size).toBe(3)
    // 不得出现"合并/重命名"式的别名
    expect(borderCollie).not.toBe(collie)
    expect(collie).not.toContain('边境')
    expect(borderTerrier).not.toContain('牧羊')
  })

  it('falls back to the raw label for unknown breeds', () => {
    // 真正不在 136 类中的标签才回退英文原名
    expect(getBreedDisplayName('not_a_real_breed')).toBe('not_a_real_breed')
    expect(getBreedDisplayName('Triceratops')).toBe('Triceratops')
  })

  it('resolves all four candidate-group labels to their panel names', () => {
    expect(CANDIDATE_GROUP).toEqual([
      'american_pit_bull_terrier',
      'american_staffordshire_terrier',
      'staffordshire_bull_terrier',
      'american_bulldog',
    ])
    expect(getBreedDisplayName('american_pit_bull_terrier'))
      .toBe('美国比特斗牛梗')
    expect(getBreedDisplayName('american_staffordshire_terrier'))
      .toBe('美国斯塔福郡梗')
    expect(getBreedDisplayName('staffordshire_bull_terrier'))
      .toBe('斯塔福郡斗牛梗')
    expect(getBreedDisplayName('american_bulldog')).toBe('美国斗牛犬')
  })

  it('handles empty input without crashing', () => {
    expect(getBreedDisplayName('')).toBe('')
    expect(getBreedDisplayName(null)).toBe('')
    expect(getBreedDisplayName(undefined)).toBe('')
  })
})

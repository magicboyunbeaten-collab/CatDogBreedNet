/**
 * Unit tests for the Chinese breed-name mapping.
 * The full-coverage test reads the REAL artifacts/class_names.json so the
 * mapping can never silently drift away from the trained labels.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  BREED_MAPPING_SIZE,
  getBreedDisplayName,
  getBreedMapping,
} from '../src/utils/breedNames'

const here = dirname(fileURLToPath(import.meta.url))
const classNames = JSON.parse(
  readFileSync(resolve(here, '../../artifacts/class_names.json'), 'utf-8'))

describe('breedNames mapping', () => {
  it('contains exactly the 37 trained class labels', () => {
    expect(BREED_MAPPING_SIZE).toBe(37)
    const mapping = getBreedMapping()
    for (const name of classNames) {
      expect(Object.prototype.hasOwnProperty.call(mapping, name)).toBe(true)
      expect(mapping[name]).toMatch(/\S/) // non-empty Chinese name
    }
  })

  it('maps cat breeds to Chinese names', () => {
    expect(getBreedDisplayName('Siamese')).toBe('暹罗猫')
    expect(getBreedDisplayName('Bengal')).toBe('孟加拉猫')
    expect(getBreedDisplayName('Persian')).toBe('波斯猫')
  })

  it('maps dog breeds to Chinese names', () => {
    expect(getBreedDisplayName('beagle')).toBe('比格犬')
    expect(getBreedDisplayName('pug')).toBe('巴哥犬')
    expect(getBreedDisplayName('samoyed')).toBe('萨摩耶犬')
  })

  it('falls back to the raw label for unknown breeds', () => {
    // Border Collie is NOT one of the 37 trained classes: it must not be
    // faked into the mapping, and it must render as the raw label.
    expect(getBreedDisplayName('border_collie')).toBe('border_collie')
    expect(getBreedDisplayName('unknown_breed')).toBe('unknown_breed')
  })

  it('handles empty input without crashing', () => {
    expect(getBreedDisplayName('')).toBe('')
    expect(getBreedDisplayName(null)).toBe('')
    expect(getBreedDisplayName(undefined)).toBe('')
  })
})

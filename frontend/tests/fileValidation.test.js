import { describe, expect, it } from 'vitest'
import { validateImageFile } from '../src/utils/fileValidation'

function makeFile(name, type, size) {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

describe('validateImageFile', () => {
  it('accepts a normal JPEG under the limit', () => {
    const result = validateImageFile(makeFile('pet.jpg', 'image/jpeg', 1024))
    expect(result.ok).toBe(true)
  })

  it('rejects missing files', () => {
    expect(validateImageFile(null).ok).toBe(false)
  })

  it('rejects empty files', () => {
    const result = validateImageFile(makeFile('pet.jpg', 'image/jpeg', 0))
    expect(result.ok).toBe(false)
    expect(result.reason).toContain('为空')
  })

  it('rejects files over 10 MB', () => {
    const result = validateImageFile(
      makeFile('big.jpg', 'image/jpeg', 11 * 1024 * 1024))
    expect(result.ok).toBe(false)
    expect(result.reason).toContain('10 MB')
  })

  it('rejects unsupported formats', () => {
    const result = validateImageFile(makeFile('anim.bmp', 'image/bmp', 1024))
    expect(result.ok).toBe(false)
    expect(result.reason).toContain('JPEG / PNG / WebP')
  })

  it('accepts webp and png', () => {
    expect(validateImageFile(makeFile('a.webp', 'image/webp', 1024)).ok).toBe(true)
    expect(validateImageFile(makeFile('b.png', 'image/png', 1024)).ok).toBe(true)
  })
})

import { describe, expect, it } from 'vitest'
import { normalizeError } from '../src/api/http'

describe('normalizeError', () => {
  it('reports network failures without a response', () => {
    const result = normalizeError({ message: 'Network Error' })
    expect(result.status).toBe(0)
    expect(result.message).toContain('无法连接')
  })

  it('reports timeouts', () => {
    const result = normalizeError({ code: 'ECONNABORTED' })
    expect(result.status).toBe(0)
    expect(result.message).toContain('超时')
  })

  it('prefers the backend error message', () => {
    const result = normalizeError({
      response: { status: 400, data: { success: false, error: 'uploaded file is empty' } }
    })
    expect(result.status).toBe(400)
    expect(result.message).toBe('uploaded file is empty')
  })

  it('supports FastAPI "detail" errors', () => {
    const result = normalizeError({
      response: { status: 422, data: { detail: 'validation error' } }
    })
    expect(result.message).toBe('validation error')
  })

  it('falls back to friendly messages per status code', () => {
    expect(normalizeError({ response: { status: 413, data: {} } }).message)
      .toContain('10 MB')
    expect(normalizeError({ response: { status: 503, data: {} } }).message)
      .toContain('模型')
    expect(normalizeError({ response: { status: 500, data: {} } }).message)
      .toContain('服务端')
    expect(normalizeError({ response: { status: 418, data: {} } }).message)
      .toContain('418')
  })
})

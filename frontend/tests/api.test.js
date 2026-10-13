import { beforeEach, describe, expect, it, vi } from 'vitest'

// Mock the shared axios instance so no real HTTP request is ever made.
vi.mock('../src/api/http', () => {
  const http = {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
  return { default: http, baseURL: 'http://127.0.0.1:8000/api' }
})

import http from '../src/api/http'
import { predictImage } from '../src/api/predict'
import { deleteHistory, fetchHistory, fetchHistoryDetail } from '../src/api/history'
import { fetchStats } from '../src/api/stats'
import { fetchHealth } from '../src/api/health'

beforeEach(() => {
  http.get.mockReset()
  http.post.mockReset()
  http.delete.mockReset()
})

describe('predictImage', () => {
  it('posts a FormData with the "file" field and top_k', async () => {
    http.post.mockResolvedValue({ data: { success: true, record_id: 1 } })
    const file = new File(['fake-bytes'], 'pet.jpg', { type: 'image/jpeg' })

    const result = await predictImage(file, 3)

    expect(http.post).toHaveBeenCalledTimes(1)
    const [url, form] = http.post.mock.calls[0]
    expect(url).toBe('/predict')
    expect(form).toBeInstanceOf(FormData)
    expect(form.get('file')).toBe(file)
    expect(form.get('top_k')).toBe('3')
    expect(result.record_id).toBe(1)
  })

  it('defaults to top-3', async () => {
    http.post.mockResolvedValue({ data: {} })
    const file = new File(['x'], 'pet.png', { type: 'image/png' })
    await predictImage(file)
    expect(http.post.mock.calls[0][1].get('top_k')).toBe('3')
  })
})

describe('history api', () => {
  it('requests history with page and page_size params', async () => {
    http.get.mockResolvedValue({ data: { items: [], total: 0 } })
    const data = await fetchHistory(2, 20)
    expect(http.get).toHaveBeenCalledWith('/history', {
      params: { page: 2, page_size: 20 }
    })
    expect(data.total).toBe(0)
  })

  it('fetches a single record', async () => {
    http.get.mockResolvedValue({ data: { item: { id: 7 } } })
    const data = await fetchHistoryDetail(7)
    expect(http.get).toHaveBeenCalledWith('/history/7')
    expect(data.item.id).toBe(7)
  })

  it('deletes a record', async () => {
    http.delete.mockResolvedValue({ data: { deleted_id: 7, image_deleted: true } })
    const data = await deleteHistory(7)
    expect(http.delete).toHaveBeenCalledWith('/history/7')
    expect(data.image_deleted).toBe(true)
  })
})

describe('stats and health api', () => {
  it('fetches stats', async () => {
    http.get.mockResolvedValue({ data: { total_predictions: 3 } })
    const data = await fetchStats()
    expect(http.get).toHaveBeenCalledWith('/stats')
    expect(data.total_predictions).toBe(3)
  })

  it('fetches health', async () => {
    http.get.mockResolvedValue({ data: { model_loaded: true } })
    const data = await fetchHealth()
    expect(http.get).toHaveBeenCalledWith('/health')
    expect(data.model_loaded).toBe(true)
  })
})

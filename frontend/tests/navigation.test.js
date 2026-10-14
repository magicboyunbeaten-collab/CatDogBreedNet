import { afterEach, describe, expect, it, vi } from 'vitest'
import { canGoBack, DEFAULT_BACK_TARGET, goBack } from '../src/utils/navigation'

/** 控制 window.history.state，模拟“有/无站内历史” */
function mockHistoryState(state) {
  vi.spyOn(window.history, 'state', 'get').mockReturnValue(state)
}

function makeFakeRouter() {
  return { back: vi.fn(), push: vi.fn() }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('canGoBack', () => {
  it('history.state.back 存在站内历史时为 true', () => {
    mockHistoryState({ back: '/predict', current: '/history' })
    expect(canGoBack()).toBe(true)
  })

  it('直接打开 URL（state 为 null）时为 false', () => {
    mockHistoryState(null)
    expect(canGoBack()).toBe(false)
  })

  it('state.back 为空/空字符串时为 false', () => {
    mockHistoryState({ back: null })
    expect(canGoBack()).toBe(false)
    mockHistoryState({ back: '' })
    expect(canGoBack()).toBe(false)
    mockHistoryState({})
    expect(canGoBack()).toBe(false)
  })
})

describe('goBack', () => {
  it('有站内历史时调用 router.back() 返回上一个页面', () => {
    mockHistoryState({ back: '/predict', current: '/history' })
    const router = makeFakeRouter()
    const result = goBack(router)
    expect(result).toBe(true)
    expect(router.back).toHaveBeenCalledTimes(1)
    expect(router.push).not.toHaveBeenCalled()
  })

  it('无站内历史时回退到默认识别页，而不是无响应', () => {
    mockHistoryState(null)
    const router = makeFakeRouter()
    const result = goBack(router)
    expect(result).toBe(false)
    expect(router.back).not.toHaveBeenCalled()
    expect(router.push).toHaveBeenCalledWith(DEFAULT_BACK_TARGET)
  })
})

describe('DEFAULT_BACK_TARGET', () => {
  it('默认回退目标是默认识别页 /predict', () => {
    expect(DEFAULT_BACK_TARGET).toBe('/predict')
  })
})

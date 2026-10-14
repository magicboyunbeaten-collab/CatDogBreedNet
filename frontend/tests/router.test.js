import { describe, expect, it } from 'vitest'
import router from '../src/router'

describe('router 路由表', () => {
  it('根路径重定向到默认识别页', () => {
    const root = router.getRoutes().find((r) => r.path === '/')
    expect(root).toBeTruthy()
    expect(root.redirect).toBe('/predict')
  })

  it('三个业务页面的名称与 meta.title 正确', () => {
    const byPath = {}
    for (const route of router.getRoutes()) byPath[route.path] = route

    expect(byPath['/predict'].name).toBe('predict')
    expect(byPath['/predict'].meta.title).toBe('图片识别')
    expect(byPath['/history'].name).toBe('history')
    expect(byPath['/history'].meta.title).toBe('识别历史')
    expect(byPath['/stats'].name).toBe('stats')
    expect(byPath['/stats'].meta.title).toBe('识别统计')
  })

  it('三个业务路径均可解析到对应组件', () => {
    for (const path of ['/predict', '/history', '/stats']) {
      const resolved = router.resolve(path)
      expect(resolved.matched.length).toBeGreaterThan(0)
      expect(typeof resolved.matched[0].components.default).toBe('object')
    }
  })

  it('默认回退目标 /predict 可解析', () => {
    const resolved = router.resolve('/predict')
    expect(resolved.name).toBe('predict')
  })
})

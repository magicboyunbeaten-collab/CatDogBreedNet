import { useRouter } from 'vue-router'

/**
 * 默认回退目标：用户直接打开某个 URL、没有可返回的站内历史时，
 * Back 按钮回退到默认识别页，而不是无响应。
 */
export const DEFAULT_BACK_TARGET = '/predict'

/**
 * 是否存在可返回的站内历史。
 *
 * vue-router 4 会在 history.state 中记录 `back`（上一次站内导航的位置）。
 * 直接打开 URL（或刷新后首次进入）时 state.back 为空，此时不存在
 * 可返回的站内页面。
 */
export function canGoBack() {
  const state = window.history.state
  return Boolean(state && typeof state.back === 'string' && state.back)
}

/**
 * 返回上一个合理的站内页面；没有站内历史时回退到默认页面。
 * 返回值：true 表示走了 router.back()，false 表示回退到了默认目标。
 */
export function goBack(router) {
  if (canGoBack()) {
    router.back()
    return true
  }
  router.push(DEFAULT_BACK_TARGET)
  return false
}

/** 便于组件直接绑定：<el-page-header @back="usePageBack()"> 的处理器工厂 */
export function usePageBack() {
  const router = useRouter()
  return () => goBack(router)
}

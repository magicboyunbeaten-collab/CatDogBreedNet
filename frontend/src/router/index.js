import { createRouter, createWebHistory } from 'vue-router'
import PredictView from '../views/PredictView.vue'
import HistoryView from '../views/HistoryView.vue'
import StatsView from '../views/StatsView.vue'

const routes = [
  { path: '/', redirect: '/predict' },
  {
    path: '/predict',
    name: 'predict',
    component: PredictView,
    meta: { title: '图片识别' }
  },
  {
    path: '/history',
    name: 'history',
    component: HistoryView,
    meta: { title: '识别历史' }
  },
  {
    path: '/stats',
    name: 'stats',
    component: StatsView,
    meta: { title: '识别统计' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} · 猫狗品种分类识别系统`
    : '猫狗品种分类识别系统'
})

export default router

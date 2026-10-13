<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-inner">
        <span class="app-title">猫狗品种分类识别系统</span>
        <el-menu
          :default-active="activeRoute"
          mode="horizontal"
          router
          class="app-menu"
        >
          <el-menu-item index="/predict">图片识别</el-menu-item>
          <el-menu-item index="/history">识别历史</el-menu-item>
          <el-menu-item index="/stats">识别统计</el-menu-item>
        </el-menu>
        <el-tag
          :type="healthTagType"
          size="small"
          class="health-tag"
          :title="healthTip"
        >
          {{ healthLabel }}
        </el-tag>
      </div>
    </el-header>

    <el-main class="app-main">
      <router-view />
    </el-main>

    <el-footer class="app-footer">
      <span>
        基于 ResNet18 的 37 类猫狗品种分类（Oxford-IIIT Pet Dataset）·
        预测分数为 Softmax 归一化分数，非真实正确概率
      </span>
    </el-footer>
  </el-container>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchHealth } from './api/health'

const route = useRoute()
const activeRoute = computed(() => route.path)

const modelLoaded = ref(null) // null = unknown, true/false from /api/health
let healthTimer = null

const healthLabel = computed(() => {
  if (modelLoaded.value === null) return '模型状态检测中'
  return modelLoaded.value ? '模型已就绪' : '模型未就绪'
})
const healthTagType = computed(() => {
  if (modelLoaded.value === null) return 'info'
  return modelLoaded.value ? 'success' : 'danger'
})
const healthTip = computed(() =>
  modelLoaded.value ? '后端模型已加载，可以发起识别' : '后端模型未加载，识别将不可用'
)

async function refreshHealth() {
  try {
    const data = await fetchHealth()
    modelLoaded.value = Boolean(data.model_loaded)
  } catch {
    modelLoaded.value = false
  }
}

onMounted(() => {
  refreshHealth()
  healthTimer = setInterval(refreshHealth, 30000)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
})
</script>

<style scoped>
.app-container {
  min-height: 100vh;
}

.app-header {
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0;
}

.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 24px;
  height: 100%;
  padding: 0 16px;
}

.app-title {
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
}

.app-menu {
  flex: 1;
  border-bottom: none;
}

.health-tag {
  white-space: nowrap;
}

.app-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
  width: 100%;
}

.app-footer {
  border-top: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

@media (max-width: 768px) {
  .header-inner {
    gap: 12px;
  }

  .app-title {
    font-size: 15px;
  }
}
</style>

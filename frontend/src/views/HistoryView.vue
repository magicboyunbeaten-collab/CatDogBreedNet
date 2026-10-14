<template>
  <div class="history-view">
    <el-page-header :icon="null" title="">
      <template #content>
        <span class="page-title">识别历史</span>
      </template>
    </el-page-header>

    <el-text class="page-desc" type="info">
      以下记录来自后端数据库的真实识别历史（时间戳为 UTC）。删除记录会同时删除服务端保存的对应图片。
    </el-text>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      :closable="false"
      show-icon
      class="history-error"
    />

    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="items"
        style="width: 100%"
        :empty-text="loadError ? '加载失败，请重试' : '暂无识别记录'"
      >
        <el-table-column prop="id" label="记录 ID" width="90" />
        <el-table-column label="图片文件" min-width="200">
          <template #default="{ row }">
            <span class="file-name" :title="row.image_filename">
              {{ row.image_filename }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="predicted_breed" label="预测品种" min-width="140" />
        <el-table-column label="置信度" width="120">
          <template #default="{ row }">
            {{ (row.confidence * 100).toFixed(2) }}%
          </template>
        </el-table-column>
        <el-table-column label="识别时间（UTC）" min-width="200">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.id)">详情</el-button>
            <el-button link type="danger" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="loadHistory"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="记录详情" width="480px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="记录 ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="图片文件">{{ detail.image_filename }}</el-descriptions-item>
        <el-descriptions-item label="预测品种">{{ detail.predicted_breed }}</el-descriptions-item>
        <el-descriptions-item label="置信度">
          {{ (detail.confidence * 100).toFixed(2) }}%
        </el-descriptions-item>
        <el-descriptions-item label="推理耗时">
          {{ detail.inference_ms.toFixed(1) }} ms
        </el-descriptions-item>
        <el-descriptions-item label="识别时间（UTC）">
          {{ formatTime(detail.created_at) }}
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="detail" class="detail-predictions">
        <div class="detail-subtitle">Top-{{ detail.predictions.length }} 预测</div>
        <div
          v-for="(item, index) in detail.predictions"
          :key="index"
          class="detail-row"
        >
          <span>{{ index + 1 }}. {{ item.breed }}</span>
          <span>{{ (item.confidence * 100).toFixed(2) }}%</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteHistory, fetchHistory, fetchHistoryDetail } from '../api/history'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const loadError = ref('')
const detailVisible = ref(false)
const detail = ref(null)

function formatTime(isoString) {
  if (!isoString) return '-'
  const date = new Date(isoString)
  if (Number.isNaN(date.getTime())) return isoString
  return date.toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z')
}

async function loadHistory() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await fetchHistory(page.value, pageSize.value)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    loadError.value = error.message || '历史记录加载失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
}

function handleSizeChange() {
  page.value = 1
  loadHistory()
}

async function openDetail(id) {
  try {
    const data = await fetchHistoryDetail(id)
    detail.value = data.item
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error.message || '记录详情加载失败')
  }
}

async function confirmDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除记录 #${row.id}（${row.predicted_breed}）吗？服务端保存的对应图片也会被删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return // user cancelled
  }
  try {
    const data = await deleteHistory(row.id)
    ElMessage.success(
      data.image_deleted ? '记录与图片已删除' : '记录已删除（图片文件未找到）'
    )
    // If the last item on the current page was removed, step back a page.
    if (items.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await loadHistory()
  } catch (error) {
    ElMessage.error(error.message || '删除失败')
  }
}

onMounted(loadHistory)
</script>

<style scoped>
.page-title {
  font-size: 20px;
  font-weight: 600;
}

.page-desc {
  display: block;
  margin: 12px 0 20px;
}

.file-name {
  font-family: monospace;
  font-size: 12px;
}

.history-error {
  margin-bottom: 16px;
}

.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-predictions {
  margin-top: 16px;
}

.detail-subtitle {
  font-weight: 600;
  margin-bottom: 8px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 14px;
}
</style>

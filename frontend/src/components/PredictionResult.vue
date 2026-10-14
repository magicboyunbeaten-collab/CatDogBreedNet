<template>
  <div v-if="result" class="prediction-result">
    <el-card shadow="never">
      <template #header>
        <div class="result-header">
          <span class="result-title">识别结果</span>
          <el-tag type="info" size="small">记录 #{{ result.record_id }}</el-tag>
        </div>
      </template>

      <div
        v-for="(item, index) in result.predictions"
        :key="index"
        class="prediction-row"
        :class="{ 'is-top': index === 0 }"
      >
        <div class="prediction-rank">{{ index === 0 ? 'Top-1' : `Top-${index + 1}` }}</div>
        <div class="prediction-breed" :title="item.breed">
          {{ getBreedDisplayName(item.breed) }}
        </div>
        <div class="prediction-score">
          <el-progress
            :percentage="Math.round(item.confidence * 1000) / 10"
            :stroke-width="14"
            :text-inside="true"
            :color="index === 0 ? '#409eff' : '#a0cfff'"
          />
          <span class="score-value">{{ (item.confidence * 100).toFixed(2) }}%</span>
        </div>
      </div>

      <el-divider border-style="dashed" />

      <div class="timing-grid">
        <div class="timing-item">
          <span class="timing-label">推理耗时</span>
          <span class="timing-value">{{ result.inference_ms.toFixed(1) }} ms</span>
        </div>
        <div class="timing-item">
          <span class="timing-label">预处理耗时</span>
          <span class="timing-value">{{ result.preprocess_ms.toFixed(1) }} ms</span>
        </div>
        <div class="timing-item">
          <span class="timing-label">服务端总耗时</span>
          <span class="timing-value">{{ result.elapsed_ms.toFixed(1) }} ms</span>
        </div>
      </div>

      <el-text size="small" type="info" class="result-note">
        {{ result.note }}；识别范围仅限训练时包含的 {{ result.num_classes }} 个品种，
        不保证能识别训练类别之外的动物、物体或无效图片。
      </el-text>
    </el-card>
  </div>
</template>

<script setup>
import { getBreedDisplayName } from '../utils/breedNames'

defineProps({
  result: {
    type: Object,
    default: null
  }
})
</script>

<style scoped>
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.result-title {
  font-weight: 600;
}

.prediction-row {
  display: grid;
  grid-template-columns: 64px 200px 1fr;
  align-items: center;
  gap: 12px;
  padding: 8px 4px;
}

.prediction-row.is-top {
  background: var(--el-color-primary-light-9);
  border-radius: 6px;
}

.prediction-rank {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.prediction-breed {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prediction-score {
  display: flex;
  align-items: center;
  gap: 10px;
}

.prediction-score :deep(.el-progress) {
  flex: 1;
}

.score-value {
  min-width: 64px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.timing-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 12px;
}

.timing-item {
  display: flex;
  flex-direction: column;
}

.timing-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.timing-value {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.result-note {
  display: block;
  line-height: 1.6;
}

@media (max-width: 640px) {
  .prediction-row {
    grid-template-columns: 56px 1fr;
  }

  .prediction-score {
    grid-column: 1 / -1;
  }
}
</style>

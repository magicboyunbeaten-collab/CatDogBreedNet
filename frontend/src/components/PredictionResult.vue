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

      <!-- 相近品种候选区：仅在候选组被触发时渲染，默认关闭时完全不出现 -->
      <el-collapse-transition>
        <div v-if="candidateTriggered" class="candidate-block">
          <div class="candidate-head">
            <span class="candidate-title">外观相近的候选品种</span>
            <span class="candidate-subtitle">{{ candidateSubtitle }}</span>
            <span class="candidate-group-id" :data-group-id="candidateGroup.group_id">
              {{ candidateGroup.group_id }}
            </span>
          </div>

          <div
            v-for="item in candidateGroup.candidates"
            :key="item.breed"
            class="candidate-row"
            :class="{ 'is-model-top': item.breed === candidateGroup.top1_breed }"
          >
            <el-radio
              :value="item.breed"
              :model-value="userChoice"
              @change="userChoice = item.breed"
            >
              <span class="candidate-name">{{ item.breed_zh }}</span>
            </el-radio>
            <div class="candidate-score">
              <el-progress
                :percentage="Math.round(item.group_score * 10) / 10"
                :stroke-width="12"
                :text-inside="true"
                color="#a0cfff"
              />
              <span class="candidate-score-value">
                {{ item.group_score.toFixed(2) }}%
              </span>
            </div>
            <span class="candidate-raw">
              原始分 {{ (item.original_confidence * 100).toFixed(2) }}%
            </span>
          </div>

          <div class="candidate-legend">
            <el-text size="small" type="info">
              候选组内相对得分（{{ candidateGroup.threshold_version }}）——
              仅在上述{{ candidateCount }}个候选之间归一化，<b>不是</b>整体识别置信度、
              真实概率或准确率；括号内为模型原始 Softmax 分数。
            </el-text>
          </div>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="candidate-note"
          >
            以下仅为外观相近品种的候选提示：单张图片未必足以可靠区分这些相近品种，
            也不保证候选中一定包含正确品种；该得分不代表模型已确认犬只的登记品种。
            你可以选择更符合的一张，该选择仅用于本次查看，不会修改模型预测与历史记录。
          </el-alert>

          <!-- 用户选择与模型预测分开呈现，互不覆盖 -->
          <div v-if="userChoice" class="user-choice">
            <span class="user-choice-label">你选择的品种</span>
            <span class="user-choice-value">
              {{ displayName(userChoice) }}
            </span>
            <el-text size="small" type="info" class="user-choice-hint">
              模型首选仍为 {{ displayName(candidateGroup.top1_breed) }}
              （原始分 {{ (candidateGroup.top1_confidence * 100).toFixed(2) }}%），未被替换。
            </el-text>
          </div>
        </div>
      </el-collapse-transition>

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
import { computed, ref, watch } from 'vue'
import { getBreedDisplayName } from '../utils/breedNames'

const props = defineProps({
  result: {
    type: Object,
    default: null
  }
})

// --- 相近品种候选组 -------------------------------------------------------
// 仅在 result.candidate_group.triggered 为真时渲染；字段缺失（功能关闭或
// V1.1 模型）时整个候选区不出现，页面与改动前完全一致。
const candidateGroup = computed(() => props.result?.candidate_group ?? null)
const candidateTriggered = computed(
  () => candidateGroup.value?.triggered === true
)

// 候选数量由后端返回的 candidates 长度决定，文案中的"N 个候选"随之变化，
// 避免把三类/四类写死导致文案与实际展示不一致。
const candidateCount = computed(
  () => candidateGroup.value?.candidates?.length ?? 0
)

// 两套并行策略的副标题：由 group_id 决定，未提供时回退到通用表述。
// 四类斗牛组与柯利/边境牧羊犬双候选组的"难以区分"含义不同，文案需如实区分。
const candidateSubtitle = computed(() => {
  const groupId = candidateGroup.value?.group_id
  if (groupId === 'collie-pair') {
    return '模型对柯利牧羊犬与边境牧羊犬难以明确区分'
  }
  if (groupId === 'four-breed-bully') {
    return '模型在这几个品种间难以明确区分'
  }
  return '模型在这几个品种间难以明确区分'
})

// 用户选择：仅存在组件内存中，不调用任何 API、不写入数据库，
// 也绝不覆盖模型原始预测（result.predictions 保持原样渲染）。
const userChoice = ref('')
watch(candidateGroup, (group) => {
  userChoice.value = group?.top1_breed ?? ''
}, { immediate: true })

const displayName = (breed) => getBreedDisplayName(breed)
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

/* --- 相近品种候选区 --- */
.candidate-block {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.candidate-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}

.candidate-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.candidate-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 候选组标识：仅用于区分两套并行策略，视觉上弱化，不干扰主要信息 */
.candidate-group-id {
  margin-left: auto;
  padding: 1px 8px;
  font-size: 11px;
  font-family: var(--el-font-family, monospace);
  letter-spacing: 0.02em;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light, #f4f4f5);
  border-radius: 10px;
}

.candidate-row {
  display: grid;
  grid-template-columns: 180px 1fr 110px;
  align-items: center;
  gap: 12px;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background-color 0.2s ease;
}

.candidate-row:hover {
  background: var(--el-color-primary-light-9);
}

.candidate-row.is-model-top {
  background: var(--el-color-primary-light-9);
}

.candidate-name {
  font-weight: 500;
}

.candidate-score {
  display: flex;
  align-items: center;
  gap: 10px;
}

.candidate-score :deep(.el-progress) {
  flex: 1;
}

.candidate-score-value {
  min-width: 62px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.candidate-raw {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.candidate-legend {
  margin-top: 8px;
  line-height: 1.6;
}

.candidate-note {
  margin-top: 8px;
}

.user-choice {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-top: 10px;
  padding: 8px 10px;
  border-left: 3px solid var(--el-color-primary);
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
}

.user-choice-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.user-choice-value {
  font-weight: 600;
}

.user-choice-hint {
  flex-basis: 100%;
}

@media (max-width: 640px) {
  .candidate-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .candidate-raw {
    text-align: right;
  }
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

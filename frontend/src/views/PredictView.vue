<template>
  <div class="predict-view">
    <el-page-header :icon="null" title="">
      <template #content>
        <span class="page-title">图片识别</span>
      </template>
      <template #extra>
        <el-button type="primary" plain @click="goHistory">查看识别历史</el-button>
      </template>
    </el-page-header>

    <el-text class="page-desc" type="info">
      上传一张猫或狗的图片，系统将基于 ResNet18 模型预测最可能的品种（Top-3）并给出 Softmax 分数。
    </el-text>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>
            <span>1. 选择图片</span>
          </template>
          <image-uploader ref="uploader" @select="handleSelect" @clear="handleClear" />

          <div class="predict-actions">
            <el-button
              type="primary"
              :loading="submitting"
              :disabled="!selectedFile || submitting"
              @click="handlePredict"
            >
              {{ submitting ? '识别中…' : '开始识别' }}
            </el-button>
            <el-button
              :disabled="submitting || (!selectedFile && !result && !errorMessage)"
              @click="handleReset"
            >
              一键清空
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card v-if="errorMessage" shadow="never" class="error-card">
          <template #header>
            <span>识别失败</span>
          </template>
          <el-alert
            :title="errorMessage"
            type="error"
            :closable="false"
            show-icon
          />
          <div class="predict-actions">
            <el-button type="primary" plain :disabled="!selectedFile" @click="handlePredict">
              重试
            </el-button>
            <el-button @click="errorMessage = ''">关闭提示</el-button>
          </div>
        </el-card>

        <prediction-result v-if="result" :result="result" />

        <el-card v-if="!result && !errorMessage" shadow="never" class="empty-card">
          <el-empty description="尚未识别，请先上传图片并点击“开始识别”" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ImageUploader from '../components/ImageUploader.vue'
import PredictionResult from '../components/PredictionResult.vue'
import { predictImage } from '../api/predict'

const router = useRouter()
const uploader = ref(null)
const selectedFile = ref(null)
const submitting = ref(false)
const result = ref(null)
const errorMessage = ref('')

function handleSelect(file) {
  selectedFile.value = file
  result.value = null
  errorMessage.value = ''
}

function handleClear() {
  selectedFile.value = null
}

async function handlePredict() {
  if (!selectedFile.value || submitting.value) return
  submitting.value = true
  errorMessage.value = ''
  result.value = null
  try {
    result.value = await predictImage(selectedFile.value, 3)
  } catch (error) {
    errorMessage.value = error.message || '识别失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function handleReset() {
  // Clear the uploader first (it emits 'clear', which nulls selectedFile),
  // then drop the previous prediction result and error state.
  uploader.value?.clearSelection()
  selectedFile.value = null
  result.value = null
  errorMessage.value = ''
}

function goHistory() {
  router.push('/history')
}
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

.predict-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.error-card,
.empty-card {
  height: 100%;
}
</style>

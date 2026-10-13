<template>
  <div class="image-uploader">
    <el-upload
      class="upload-dragger"
      drag
      :auto-upload="false"
      :show-file-list="false"
      :accept="acceptAttr"
      :on-change="handleChange"
      :on-exceed="handleExceed"
      :limit="1"
    >
      <div v-if="!previewUrl" class="upload-placeholder">
        <el-icon class="upload-icon"><upload-filled /></el-icon>
        <div class="upload-text">将图片拖到此处，或 <em>点击上传</em></div>
        <div class="upload-tip">仅支持 JPEG / PNG / WebP，且不超过 10 MB</div>
      </div>
      <div v-else class="upload-preview">
        <img :src="previewUrl" alt="已选择的图片预览" class="preview-image" />
        <div class="preview-meta">
          <span class="preview-name">{{ selectedName }}</span>
          <span class="preview-size">{{ selectedSize }}</span>
        </div>
      </div>
    </el-upload>

    <div v-if="previewUrl" class="upload-actions">
      <el-button size="small" @click="clearSelection">移除图片</el-button>
      <el-button size="small" @click="triggerReselect">重新选择</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { validateImageFile } from '../utils/fileValidation'

const emit = defineEmits(['select', 'clear'])

const acceptAttr = '.jpg,.jpeg,.png,.webp'
const selectedFile = ref(null)
const previewUrl = ref('')

const selectedName = computed(() => selectedFile.value?.name || '')
const selectedSize = computed(() => {
  const size = selectedFile.value?.size || 0
  return `${(size / 1024).toFixed(0)} KB`
})

function releasePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

function handleChange(file) {
  const raw = file.raw || file
  const check = validateImageFile(raw)
  if (!check.ok) {
    ElMessage.warning(check.reason)
    clearSelection()
    return
  }
  releasePreview()
  selectedFile.value = raw
  previewUrl.value = URL.createObjectURL(raw)
  emit('select', raw)
}

function handleExceed() {
  ElMessage.warning('只能选择一张图片，请先移除当前图片')
}

function clearSelection() {
  releasePreview()
  selectedFile.value = null
  emit('clear')
}

function triggerReselect() {
  // Re-open the file dialog through a fresh upload trigger.
  const input = document.querySelector('.upload-dragger input[type="file"]')
  if (input) {
    input.value = ''
    input.click()
  }
}

// Defensive: release the object URL when the parent swaps files or unmounts.
watch(previewUrl, (newUrl, oldUrl) => {
  if (oldUrl && oldUrl !== newUrl) URL.revokeObjectURL(oldUrl)
})

onBeforeUnmount(releasePreview)

defineExpose({ clearSelection })
</script>

<style scoped>
.upload-dragger {
  width: 100%;
}

.upload-placeholder {
  padding: 24px 16px;
}

.upload-icon {
  font-size: 40px;
  color: var(--el-text-color-placeholder);
}

.upload-text {
  margin-top: 8px;
  font-size: 14px;
}

.upload-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.upload-preview {
  padding: 12px;
}

.preview-image {
  max-width: 100%;
  max-height: 320px;
  object-fit: contain;
  border-radius: 6px;
}

.preview-meta {
  margin-top: 8px;
  display: flex;
  gap: 12px;
  justify-content: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.preview-name {
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  justify-content: center;
}
</style>

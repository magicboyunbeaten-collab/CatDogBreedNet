<template>
  <div class="image-uploader">
    <el-upload
      ref="uploadRef"
      class="upload-dragger"
      drag
      :auto-upload="false"
      :show-file-list="false"
      :multiple="false"
      :accept="acceptAttr"
      :on-change="handleChange"
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
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { validateImageFile } from '../utils/fileValidation'

const emit = defineEmits(['select', 'clear'])

const acceptAttr = '.jpg,.jpeg,.png,.webp'
const uploadRef = ref(null)
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

// The native <input type="file"> rendered inside el-upload.
function getNativeInput() {
  const upload = uploadRef.value
  if (!upload) return null
  return upload.$refs?.input
    || upload.$el?.querySelector('input[type="file"]')
    || null
}

// Reset the native input so choosing the *same* file again fires `change`.
function resetNativeInput() {
  const input = getNativeInput()
  if (input) input.value = ''
}

// Drop the file entry el-upload keeps internally (and reset the native
// input) so the picker stays reusable without a page refresh.
function resetPicker() {
  uploadRef.value?.clearFiles()
  resetNativeInput()
}

function handleChange(file) {
  // 1) Safely capture the user's File object first.
  const raw = file?.raw || file
  const check = validateImageFile(raw)
  if (!check.ok) {
    // 2) Rejected file: drop it from the picker but keep any previous
    //    valid selection untouched.
    ElMessage.warning(check.reason)
    nextTick(resetPicker)
    return
  }
  // 3) Accept: swap preview (releasing the old object URL) and notify.
  releasePreview()
  selectedFile.value = raw
  previewUrl.value = URL.createObjectURL(raw)
  emit('select', raw)
  // 4) Keep the picker reusable: clear el-upload's internal file list and
  //    reset the native input after el-upload finished its own handling.
  nextTick(resetPicker)
}

function clearSelection() {
  releasePreview()
  selectedFile.value = null
  resetPicker()
  emit('clear')
}

function triggerReselect() {
  // Reset everything first, then open a fresh file dialog.
  clearSelection()
  nextTick(() => {
    getNativeInput()?.click()
  })
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

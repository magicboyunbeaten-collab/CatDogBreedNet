// Client-side pre-check for uploads. The server-side validation in the
// backend is always the final authority; this only fails fast on obvious
// problems (mirrors backend defaults: 10 MB, JPEG/PNG/WebP).

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024
export const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']

export function validateImageFile(file) {
  if (!file) {
    return { ok: false, reason: '请先选择图片文件' }
  }
  if (file.size === 0) {
    return { ok: false, reason: '文件为空，请重新选择图片' }
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      reason: `文件大小 ${(file.size / 1024 / 1024).toFixed(1)} MB 超过 10 MB 上限`
    }
  }
  const name = (file.name || '').toLowerCase()
  const extOk = ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))
  const typeOk = ALLOWED_TYPES.includes(file.type)
  if (!extOk && !typeOk) {
    return { ok: false, reason: '仅支持 JPEG / PNG / WebP 格式的图片' }
  }
  return { ok: true }
}

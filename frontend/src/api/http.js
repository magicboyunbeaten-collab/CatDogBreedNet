import axios from 'axios'

// Backend base URL comes from the environment (see .env.example).
// The fallback keeps the app usable when .env.development is missing.
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

const http = axios.create({
  baseURL,
  timeout: 30000
})

const FALLBACK_MESSAGES = {
  400: '请求不合法：文件可能为空、格式不支持、已损坏或参数越界',
  413: '文件超过大小上限（10 MB）',
  500: '服务端处理失败，请稍后重试',
  503: '模型尚未就绪，请稍后重试'
}

// Turn any axios error into a flat, client-safe { status, message }.
export function normalizeError(error) {
  if (error && error.code === 'ECONNABORTED') {
    return { status: 0, message: '请求超时，请检查网络或后端服务' }
  }
  if (!error || !error.response) {
    return { status: 0, message: '无法连接后端服务，请确认服务已启动' }
  }
  const status = error.response.status
  const data = error.response.data || {}
  // Backend errors are { success: false, error: "..." }; FastAPI validation
  // errors use "detail". Never expose raw internals to the UI.
  const serverMessage = typeof data.error === 'string' ? data.error
    : typeof data.detail === 'string' ? data.detail
      : null
  return {
    status,
    message: serverMessage || FALLBACK_MESSAGES[status] || `请求失败（HTTP ${status}）`
  }
}

http.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(normalizeError(error))
)

export { baseURL }
export default http

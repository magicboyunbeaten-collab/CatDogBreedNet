import http from './http'

// GET /api/history?page=1&page_size=10 (server-side pagination)
export function fetchHistory(page = 1, pageSize = 10) {
  return http
    .get('/history', { params: { page, page_size: pageSize } })
    .then((response) => response.data)
}

// GET /api/history/{id}
export function fetchHistoryDetail(recordId) {
  return http.get(`/history/${recordId}`).then((response) => response.data)
}

// DELETE /api/history/{id}
export function deleteHistory(recordId) {
  return http.delete(`/history/${recordId}`).then((response) => response.data)
}

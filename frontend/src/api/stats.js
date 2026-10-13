import http from './http'

// GET /api/stats - all numbers come from real database records
export function fetchStats() {
  return http.get('/stats').then((response) => response.data)
}

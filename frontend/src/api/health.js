import http from './http'

// GET /api/health - model readiness for the header status indicator
export function fetchHealth() {
  return http.get('/health').then((response) => response.data)
}

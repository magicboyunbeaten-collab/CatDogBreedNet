import http from './http'

// POST /api/predict - multipart/form-data, field name "file" (backend contract).
// Axios sets the multipart Content-Type (with boundary) automatically.
export function predictImage(file, topK = 3) {
  const form = new FormData()
  form.append('file', file)
  form.append('top_k', String(topK))
  return http.post('/predict', form).then((response) => response.data)
}

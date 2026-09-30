import axios from 'axios'

const http = axios.create({ baseURL: '/api' })
const bare = axios.create({ baseURL: '/api' }) // no interceptors, used for refresh

let refreshing = null

http.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

http.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config
    const url = original?.url || ''
    const skip = url.includes('/auth/login') || url.includes('/auth/refresh')

    if (err.response?.status === 401 && original && !original._retry && !skip) {
      original._retry = true
      try {
        refreshing = refreshing || bare.post('/auth/refresh').finally(() => (refreshing = null))
        const { data } = await refreshing
        localStorage.setItem('token', data.access_token)
        return http(original) // request interceptor attaches the new token
      } catch {
        localStorage.removeItem('token')
        if (location.pathname !== '/login') location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)

export function errorMessage(e) {
  const d = e.response?.data?.detail
  if (Array.isArray(d)) return d.map((x) => x.msg).join(', ')
  return d || 'Something went wrong'
}

export default http
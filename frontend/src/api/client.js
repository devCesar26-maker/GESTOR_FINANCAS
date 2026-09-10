import axios from 'axios'

// Todas as chamadas passam pelo proxy do Vite (mesma origem em dev),
// então a base é apenas '/api'.
const api = axios.create({
  baseURL: '/api',
})

// Injeta o access token JWT em todas as requisições.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('finflow_access')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Em 401 (token expirado/inválido) limpa a sessão e volta para o login.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('finflow_access')
      localStorage.removeItem('finflow_refresh')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export default api
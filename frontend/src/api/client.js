import axios from 'axios'

// Todas as chamadas passam pelo proxy do Vite (mesma origem em dev),
// então a base é apenas '/api'.
const api = axios.create({
  baseURL: '/api',
})

// ---------------------------------------------------------------------------
// Access token EM MEMÓRIA (anti-exfiltração via XSS)
// ---------------------------------------------------------------------------
// O access token NUNCA toca localStorage/sessionStorage/cookies: vive apenas
// nesta variável de módulo. Um XSS consegue lê-lo em runtime, mas não consegue
// PERSISTIR a sessão — ao recarregar a página o token se perde e a sessão é
// reidratada pelo silent refresh (cookie httpOnly), ver initAuth() abaixo.

let accessToken = null

export function setAccessToken(token) {
  accessToken = token
}

export function getAccessToken() {
  return accessToken
}

export function clearAccessToken() {
  accessToken = null
}

// ---------------------------------------------------------------------------
// Silent refresh (reidratação da sessão no bootstrap)
// ---------------------------------------------------------------------------
// Faz POST /api/token/refresh/ sem corpo: o refresh token viaja EXCLUSIVAMENTE
// no cookie httpOnly (path restrito a /api/token/refresh/) e o CSRF vai no
// header X-CSRFToken (duplo envio). Single-flight: chamadas simultâneas (ex:
// StrictMode montando efeitos duas vezes) compartilham a MESMA promessa — e a
// promessa resolvida é mantida para não re-refreshar em todo remount.

let initPromise = null

export function initAuth() {
  if (!initPromise) {
    initPromise = (async () => {
      try {
        // Garante o cookie csrftoken antes do POST (o httpOnly de refresh
        // não basta: o backend exige o duplo envio CSRF). Se o cookie já
        // existe, NENHUMA requisição extra acontece.
        await garantirCsrfToken()

        // Rota pública: um 401/403 aqui NÃO dispara o fluxo de renovação do
        // interceptor de resposta — a exceção chega direto neste catch.
        const response = await api.post('/token/refresh/')
        accessToken = response.data.access
        return true
      } catch {
        // Sem sessão (refresh cookie ausente/expirado) ou backend fora do ar:
        // usuário NÃO autenticado. Limpa memória — o redirecionamento para
        // /login é decisão da UI (RequireAuth), não do cliente HTTP.
        accessToken = null
        return false
      }
    })()
  }
  return initPromise
}

// ---------------------------------------------------------------------------
// Refresh automático de JWT
// ---------------------------------------------------------------------------
// Endpoints que NÃO usam autenticação (login, refresh, registro): um 401
// deles significa credencial inválida, não token expirado — nunca se deve
// tentar renovar a sessão por causa dessas respostas.
const RUTAS_PUBLICAS = ['/token/', '/token/refresh/', '/auth/registro/']

function esRutaPublica(url) {
  return RUTAS_PUBLICAS.some((ruta) => url?.includes(ruta))
}

// ---------------------------------------------------------------------------
// CSRF (duplo envio: cookie csrftoken + header X-CSRFToken)
// ---------------------------------------------------------------------------
// O backend exige o header X-CSRFToken em toda escrita em rota com cookie de
// credencial (login e refresh — ver CsrfViewMiddleware + csrf_protect). O
// cookie csrftoken NÃO é httpOnly: o JS o lê e devolve no header.

function lerCookie(nome) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + nome + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : null
}

// Devolve o valor ATUAL do cookie csrftoken; só dispara GET /api/csrf/ se o
// cookie ainda não existe. O cookie pode rotar no backend, então o valor é
// lido do document.cookie a cada escrita (barato e sempre atual) — o cache
// é apenas do FETCH em voo, para chamadas simultâneas não dispararem
// vários GET /api/csrf/ (single-flight).
let csrfFetchPromise = null

function garantirCsrfToken() {
  const token = lerCookie('csrftoken')
  if (token) return Promise.resolve(token)

  if (!csrfFetchPromise) {
    csrfFetchPromise = axios
      .get('/api/csrf/')
      // axios "pelado": sem interceptores (GET não passaria por eles mesmo,
      // mas evitamos acoplamento com a instância `api`).
      .then(() => lerCookie('csrftoken'))
      .finally(() => {
        // Libera para nova tentativa se o cookie não tiver sido setado.
        csrfFetchPromise = null
      })
  }
  return csrfFetchPromise
}

function limpiarSesion() {
  accessToken = null
  // Chaves LEGADAS do fluxo antigo (access/refresh em localStorage): removidas
  // para limpar resíduos de sessões anteriores à migração para memória.
  localStorage.removeItem('finflow_access')
  localStorage.removeItem('finflow_refresh')
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

// Renova o access token. O refresh token NUNCA é enviado pelo JS: o backend
// o lê do cookie httpOnly (path restrito a /api/token/refresh/). Usa a
// instância `api` (com interceptores): a rota é pública, então um 401 aqui
// não dispara re-refresh — é isso que evita o loop infinito.
let refreshPromise = null

function renovarAccessToken() {
  if (refreshPromise) return refreshPromise

  refreshPromise = api
    .post('/token/refresh/')
    .then((response) => {
      accessToken = response.data.access
      return accessToken
    })
    .catch((error) => {
      // Refresh token expirado/inválido: a sessão não serve mais.
      limpiarSesion()
      throw error
    })
    .finally(() => {
      refreshPromise = null
    })

  return refreshPromise
}

// ---------------------------------------------------------------------------
// Interceptores
// ---------------------------------------------------------------------------

const METODOS_COM_CSRF = new Set(['post', 'put', 'patch', 'delete'])

// Injeta o access token JWT (da memória) e (em escritas) o X-CSRFToken.
api.interceptors.request.use(async (config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  if (METODOS_COM_CSRF.has((config.method || 'get').toLowerCase())) {
    // Toda escrita leva o duplo envio CSRF: obrigatório em /token/* (o
    // backend devolve 403 sem o header) e inofensivo nas demais rotas.
    const csrf = await garantirCsrfToken()
    if (csrf) {
      config.headers['X-CSRFToken'] = csrf
    }
  }

  return config
})

// Em 401: tenta renovar o token UNA vez e repete a requisição original de
// forma transparente. Se o refresh falha, limpa a sessão e volta ao login.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config
    const status = error.response?.status

    if (
      status === 401 &&
      config &&
      !config._retried && // já foi reintentada uma vez: nunca em loop
      !esRutaPublica(config.url)
    ) {
      config._retried = true
      try {
        await renovarAccessToken()
        // Repete a requisição original: o request interceptor volta a
        // executar e adjunta o access token recém renovado.
        return api.request(config)
      } catch {
        // renovarAccessToken já limpou a sessão e redirigiu a /login.
        throw error
      }
    }

    throw error
  },
)

export default api

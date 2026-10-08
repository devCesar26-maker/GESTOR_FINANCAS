import axios from 'axios'

// ---------------------------------------------------------------------------
// Origem da API (deploy Render: SPA e API em subdomínios DIFERENTES)
// ---------------------------------------------------------------------------
// Em dev (e no docker-compose) as chamadas passam pelo proxy do Vite (mesma
// origem): VITE_API_URL não existe e API_ORIGIN fica vazio — baseURL é
// apenas '/api', como sempre. No Render, VITE_API_URL é definida no BUILD
// (variável VITE_* do Vite é embutida no bundle; ver render.yaml).
// Tolerante ao formato: aceita com ou sem "https://" (o fromService
// property: host do Render devolve só o domínio) e com ou sem sufixo "/api".
const rawApiUrl = (import.meta.env?.VITE_API_URL || '').trim()
let comEsquema = /^[a-z][a-z0-9+.-]*:\/\//i.test(rawApiUrl)
  ? rawApiUrl
  : rawApiUrl
    ? `https://${rawApiUrl}`
    : ''

if (
  comEsquema &&
  !comEsquema.includes('.') &&
  typeof window !== 'undefined' &&
  window.location.hostname.endsWith('.onrender.com')
) {
  comEsquema = `${comEsquema}.onrender.com`
}

const API_ORIGIN = comEsquema.replace(/\/+$/, '').replace(/\/api\/?$/i, '')

// Origem do backend para recursos FORA de /api (ex.: download de comprovantes
// em /media/... com JWT no header — ver Faturas.jsx). Vazio em dev.
export const BACKEND_ORIGIN = API_ORIGIN

const api = axios.create({
  baseURL: `${API_ORIGIN}/api`,
  // Deploy cross-origin (SPA e API em subdomínios diferentes): sem isto o
  // navegador NÃO envia nem guarda os cookies da API (csrftoken e o httpOnly
  // do refresh token) — o login/refresh quebraria. Em dev (same-origin via
  // proxy Vite) a flag é inofensiva.
  withCredentials: true,
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
// Endpoints que NÃO usam autenticação (login, refresh, registro, reset de
// senha e Google): um 401 deles significa credencial inválida, não token
// expirado — nunca se deve tentar renovar a sessão por causa dessas respostas.
const RUTAS_PUBLICAS = [
  '/token/',
  '/token/refresh/',
  '/auth/registro/',
  '/auth/password/reset/',
  '/auth/google/',
]

function esRutaPublica(url) {
  return RUTAS_PUBLICAS.some((ruta) => url?.includes(ruta))
}

// ---------------------------------------------------------------------------
// Login/Cadastro com Google (OAuth 2.0 via id_token)
// ---------------------------------------------------------------------------
// O botão oficial do Google (GoogleLogin de @react-oauth/google) entrega o
// id_token (JWT assinado pelo Google) e nós o trocamos pelos JWTs nativos
// do FinFlow: access token no retorno (memória) e refresh token no cookie
// httpOnly — exatamente o mesmo contrato do login por senha.
export async function loginComGoogle(idToken) {
  const response = await api.post('/auth/google/', { id_token: idToken })
  // Mesma semântica do handleSubmit do Login: token só em memória; o
  // refresh chega num cookie httpOnly setado pelo backend.
  accessToken = response.data.access
  return response.data
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

// Deploy CROSS-ORIGIN (Render: SPA e API em subdomínios diferentes): o JS da
// SPA não consegue ler o cookie csrftoken do domínio da API (Same-Origin
// Policy). O backend então entrega o segredo CSRF cru no header de resposta
// X-CSRFSecret do GET /api/csrf/ (exposto à SPA via CORS_EXPOSE_HEADERS) e
// aceita a dupla chave segredo (header X-CSRFSecret) + cookie (que só o
// navegador da origem autorizada envia). Mesma origem (dev), o cookie é
// legível e este segredo simplesmente não é necessário.
let csrfSecret = null

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
    csrfFetchPromise = api
      .get('/csrf/')
      // Via PELA INSTÂNCIA api (baseURL certa no Render); em dev é igual a
      // GET /api/csrf/ de antes. Seguro contra loop: o interceptor só chama
      // garantirCsrfToken em métodos de ESCRITA, e este é um GET.
      .then((response) => {
        // Cross-origin: o cookie da API não é legível — o segredo vem no
        // header de resposta (axios normaliza o nome para minúsculas).
        // Semeamos o cookie local para o bootstrap não refazer o GET em cada
        // escrita (o backend também seta o cookie REAL via Set-Cookie, que o
        // navegador guarda mesmo sem o JS conseguir lê-lo).
        const segredo = response.headers?.['x-csrfsecret']
        if (segredo) {
          csrfSecret = segredo
          document.cookie = `csrftoken=${segredo}; path=/`
        }
        return lerCookie('csrftoken')
      })
      .finally(() => {
        // Libera para nova tentativa se o cookie não tiver sido setado.
        csrfFetchPromise = null
      })
  }
  return csrfFetchPromise
}

// Limpeza local do CSRF (logout/expiração): o par cookie/segredo continua
// válido no backend enquanto o cookie csrftoken for válido — mesmo modelo do
// duplo envio clássico, em que o JS reenvia o MESMO valor do cookie.
function invalidarCsrfLocal() {
  csrfSecret = null
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
}

function limpiarSesion() {
  accessToken = null
  invalidarCsrfLocal()
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

// Injeta o access token JWT (da memória) e (em escritas) o duplo envio CSRF.
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
    // Cross-origin: o cookie csrftoken da API não é legível pela SPA, então
    // o duplo envio clássico é impossível — envia o segredo recebido no body
    // de GET /api/csrf/ (o backend valida a dupla chave segredo + cookie).
    if (csrfSecret) {
      config.headers['X-CSRFSecret'] = csrfSecret
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

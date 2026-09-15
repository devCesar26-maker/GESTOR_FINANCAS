import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  localStorage.clear()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})
afterAll(() => server.close())

// vi.resetModules() + import dinâmico: o estado do client (access token em
// memória, promessas single-flight) é de ESCOPO DE MÓDULO — recarregar o
// módulo a cada teste garante isolamento total (um teste nunca herda o
// token/sessão do anterior).
async function carregarClient() {
  vi.resetModules()
  return await import('./client')
}

// Semeia o cookie csrftoken como o navegador faria após GET /api/csrf/.
// (msw/node não executa cookies de verdade — sem isso o interceptor disparia
// um GET /api/csrf/ de verdade, que precisaria ser mockado.)
function semearCsrf(token = 'csrf-de-teste') {
  document.cookie = `csrftoken=${token}; path=/`
  return token
}

// ===========================================================================
// Access token em memória (nada em localStorage)
// ===========================================================================

describe('access token em memória', () => {
  it('set/get/clear manipulam o token sem tocar no localStorage', async () => {
    const client = await carregarClient()

    expect(client.getAccessToken()).toBeNull()
    client.setAccessToken('token-memoria')
    expect(client.getAccessToken()).toBe('token-memoria')
    client.clearAccessToken()
    expect(client.getAccessToken()).toBeNull()

    expect(localStorage.getItem('finflow_access')).toBeNull()
    expect(localStorage.getItem('finflow_refresh')).toBeNull()
  })
})

// ===========================================================================
// Silent refresh na inicialização (initAuth)
// ===========================================================================

describe('initAuth (silent refresh no bootstrap)', () => {
  it('reidrata o access token em memória via cookie httpOnly (POST sem body)', async () => {
    const csrf = semearCsrf()
    let refreshCalls = 0
    let refreshBody = undefined
    server.use(
      http.post('/api/token/refresh/', async ({ request }) => {
        refreshCalls += 1
        expect(request.headers.get('X-CSRFToken')).toBe(csrf)
        refreshBody = await request.text()
        return HttpResponse.json({ access: 'access-reidratado' })
      }),
    )

    const client = await carregarClient()
    const autenticado = await client.initAuth()

    expect(autenticado).toBe(true)
    expect(refreshCalls).toBe(1)
    expect(refreshBody).toBe('') // refresh token NUNCA viaja no body
    expect(client.getAccessToken()).toBe('access-reidratado')
    expect(localStorage.getItem('finflow_access')).toBeNull()
    expect(localStorage.getItem('finflow_refresh')).toBeNull()
  })

  it('sem sessão válida: limpa a memória e marca como não autenticado (sem loop)', async () => {
    semearCsrf()
    let refreshCalls = 0
    server.use(
      http.post('/api/token/refresh/', () => {
        refreshCalls += 1
        return new HttpResponse(null, { status: 401 })
      }),
    )

    const client = await carregarClient()
    client.setAccessToken('token-velho')

    await expect(client.initAuth()).resolves.toBe(false)

    expect(refreshCalls).toBe(1) // uma única tentativa, sem loop
    expect(client.getAccessToken()).toBeNull()
  })

  it('chamadas simultâneas compartilham a mesma promessa (StrictMode)', async () => {
    semearCsrf()
    let refreshCalls = 0
    server.use(
      http.post('/api/token/refresh/', () => {
        refreshCalls += 1
        return HttpResponse.json({ access: 'access-reidratado' })
      }),
    )

    const client = await carregarClient()
    const [a, b, c] = await Promise.all([client.initAuth(), client.initAuth(), client.initAuth()])

    expect(refreshCalls).toBe(1)
    expect(a).toBe(true)
    expect(b).toBe(true)
    expect(c).toBe(true)
  })
})

// ===========================================================================
// Interceptores (token da memória + CSRF de duplo envio)
// ===========================================================================

describe('interceptor de refresh automático de JWT', () => {
  it('renova o token e reintenta a requisição original com o novo access token', async () => {
    const csrf = semearCsrf()
    let refreshCalls = 0
    let clientesCalls = 0
    server.use(
      http.post('/api/token/refresh/', ({ request }) => {
        expect(request.headers.get('X-CSRFToken')).toBe(csrf)
        refreshCalls += 1
        return HttpResponse.json({ access: 'access-novo' })
      }),
      http.get('/api/clientes/', ({ request }) => {
        clientesCalls += 1
        if (clientesCalls === 1) {
          return new HttpResponse(null, { status: 401 })
        }
        // O reintento deve levar o token recém renovado.
        expect(request.headers.get('Authorization')).toBe('Bearer access-novo')
        return HttpResponse.json({ results: [] })
      }),
    )

    const client = await carregarClient()
    client.setAccessToken('access-antigo')

    const response = await client.default.get('/clientes/')

    expect(clientesCalls).toBe(2) // 1º 401 + reintento transparente
    expect(refreshCalls).toBe(1)
    expect(client.getAccessToken()).toBe('access-novo') // atualizado EM memória
    expect(localStorage.getItem('finflow_access')).toBeNull() // nunca persistido
    expect(response.status).toBe(200)
  })

  it('múltiplas requisições 401 simultâneas disparam uma única chamada de refresh', async () => {
    semearCsrf()
    let refreshCalls = 0
    const calls = { clientes: 0, faturas: 0, dashboard: 0 }
    server.use(
      http.post('/api/token/refresh/', () => {
        refreshCalls += 1
        return HttpResponse.json({ access: 'access-novo' })
      }),
      http.get('/api/clientes/', () => {
        calls.clientes += 1
        return calls.clientes === 1
          ? new HttpResponse(null, { status: 401 })
          : HttpResponse.json({ results: [] })
      }),
      http.get('/api/faturas/', () => {
        calls.faturas += 1
        return calls.faturas === 1
          ? new HttpResponse(null, { status: 401 })
          : HttpResponse.json({ results: [] })
      }),
      http.get('/api/dashboard/', () => {
        calls.dashboard += 1
        return calls.dashboard === 1
          ? new HttpResponse(null, { status: 401 })
          : HttpResponse.json({ results: [] })
      }),
    )

    const client = await carregarClient()
    client.setAccessToken('access-antigo')

    const [clientes, faturas, dashboard] = await Promise.all([
      client.default.get('/clientes/'),
      client.default.get('/faturas/'),
      client.default.get('/dashboard/'),
    ])

    expect(refreshCalls).toBe(1) // single-flight: uma única chamada de refresh
    expect(clientes.status).toBe(200)
    expect(faturas.status).toBe(200)
    expect(dashboard.status).toBe(200)
  })

  it('se o refresh falha, limpa a sessão e redireciona a /login sem loop', async () => {
    semearCsrf()
    let refreshCalls = 0
    server.use(
      http.post('/api/token/refresh/', () => {
        refreshCalls += 1
        return new HttpResponse(null, { status: 401 })
      }),
      http.get('/api/clientes/', () => new HttpResponse(null, { status: 401 })),
    )

    // Captura o redirect em vez de deixar jsdom "navegar" de verdade
    // (jsdom não navega de verdade: só emite um warning no console).
    let redirectedTo = null
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        pathname: '/dashboard',
        get href() {
          return 'http://localhost' + this.pathname
        },
        set href(value) {
          redirectedTo = value
        },
      },
    })

    const client = await carregarClient()
    client.setAccessToken('access-antigo')

    await expect(client.default.get('/clientes/')).rejects.toThrow()

    expect(refreshCalls).toBe(1) // sem loop infinito
    expect(client.getAccessToken()).toBeNull()
    expect(redirectedTo).toBe('/login')
  })

  it('um 401 no login não dispara refresh (credenciais inválidas ≠ token expirado)', async () => {
    const csrf = semearCsrf()
    let refreshCalls = 0
    let loginCsrfHeader = null
    server.use(
      http.post('/api/token/refresh/', () => {
        refreshCalls += 1
        return HttpResponse.json({ access: 'access-novo' })
      }),
      http.post('/api/token/', ({ request }) => {
        loginCsrfHeader = request.headers.get('X-CSRFToken')
        return new HttpResponse(null, { status: 401 })
      }),
    )

    const client = await carregarClient()
    client.setAccessToken('access-antigo')

    await expect(
      client.default.post('/token/', { username: 'x', password: 'y' }),
    ).rejects.toThrow()

    expect(refreshCalls).toBe(0)
    expect(client.getAccessToken()).toBe('access-antigo') // sessão intacta
    expect(loginCsrfHeader).toBe(csrf) // duplo envio presente mesmo assim
  })

  it('toda requisição de escrita envia o header X-CSRFToken (duplo envio)', async () => {
    const csrf = semearCsrf()
    let headersVistos = null
    server.use(
      http.post('/api/clientes/', ({ request }) => {
        headersVistos = {
          csrf: request.headers.get('X-CSRFToken'),
          auth: request.headers.get('Authorization'),
        }
        return HttpResponse.json({ id: 1 }, { status: 201 })
      }),
    )

    const client = await carregarClient()
    client.setAccessToken('access-antigo')

    await client.default.post('/clientes/', { nome: 'Teste' })

    expect(headersVistos.csrf).toBe(csrf)
    expect(headersVistos.auth).toBe('Bearer access-antigo')
  })
})

// ===========================================================================
// Bootstrap do csrftoken: busca o cookie quando ele ainda não existe
// ===========================================================================

describe('bootstrap do csrftoken', () => {
  it('sem cookie csrftoken, a primeira escrita busca GET /api/csrf/ e reenvia', async () => {
    let csrfCalls = 0
    server.use(
      http.get('/api/csrf/', () => {
        csrfCalls += 1
        // Em produção o Set-Cookie vem do backend; aqui plantamos o cookie
        // na resposta para o interceptor encontrar na releitura.
        document.cookie = 'csrftoken=csrf-fresco; path=/'
        return new HttpResponse(null, { status: 204 })
      }),
      http.post('/api/clientes/', ({ request }) => {
        return HttpResponse.json({ csrf: request.headers.get('X-CSRFToken') }, { status: 201 })
      }),
    )

    const client = await carregarClient()

    const response = await client.default.post('/clientes/', { nome: 'Teste' })

    expect(csrfCalls).toBe(1)
    expect(response.data.csrf).toBe('csrf-fresco')
  })

  it('chamadas simultâneas sem cookie disparam UMA única chamada a /api/csrf/', async () => {
    let csrfCalls = 0
    server.use(
      http.get('/api/csrf/', () => {
        csrfCalls += 1
        document.cookie = 'csrftoken=csrf-fresco; path=/'
        return new HttpResponse(null, { status: 204 })
      }),
      http.post('/api/clientes/', () => HttpResponse.json({ id: 1 }, { status: 201 })),
    )

    const client = await carregarClient()

    await Promise.all([
      client.default.post('/clientes/', { nome: 'A' }),
      client.default.post('/clientes/', { nome: 'B' }),
    ])

    expect(csrfCalls).toBe(1) // single-flight do fetch de CSRF
  })
})

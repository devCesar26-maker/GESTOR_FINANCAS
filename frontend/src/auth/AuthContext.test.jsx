import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import App from '../App'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

// vi.resetModules() + import dinâmico: o estado do client (access token em
// memória e promessas single-flight) é de ESCOPO DE MÓDULO — recarregar a
// cada teste garante isolamento entre os casos.
async function carregarApp() {
  vi.resetModules()
  const auth = await import('./AuthContext')
  const app = await import('../App')
  return { ...auth, App: app.default }
}

function semearCsrf(token = 'csrf-de-teste') {
  document.cookie = `csrftoken=${token}; path=/`
  return token
}

// Renderiza <AuthProvider><App/></AuthProvider> em MemoryRouter e devolve
// o pathname TARDIO (após o fetch de bootstrap resolver). Também conta as
// chamadas de refresh (para garantir exatamente UMA tentativa por F5).
async function montarAppComBootstrap(rotaInicial, msw) {
  if (msw) msw.forEach((h) => server.use(h))
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)

  const { AuthProvider: Provider, App: AppFinal } = await carregarApp()
  let refreshCalls = 0

  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={[rotaInicial]}>
        <Provider>
          <AppFinal />
        </Provider>
      </MemoryRouter>,
    )
  })

  return {
    root,
    container,
    refreshCalls: () => refreshCalls,
    unmount: () => {
      act(() => root.unmount())
      container.remove()
    },
  }
}

function SondeAuth() {
  const { loading, autenticado } = useAuth()
  return (
    <div data-testid="auth-state">
      {JSON.stringify({ loading, autenticado })}
    </div>
  )
}

describe('AuthProvider (restauração de sessão no mount)', () => {
  it('F5 com refresh token válido: silent refresh reidrata o access token e a rota protegida NÃO manda ao login', async () => {
    semearCsrf()
    let refreshCalls = 0
    const auth = await montarAppComBootstrap('/', [
      http.post('/api/token/refresh/', () => {
        refreshCalls += 1
        return HttpResponse.json({ access: 'access-f5' })
      }),
      http.get('/api/relatorios/fluxo-caixa/', () =>
        HttpResponse.json({ receitas: [], despesas: [] }),
      ),
      http.get('/api/relatorios/dre/', () => HttpResponse.json({ receitas: [], despesas: [] })),
    ])

    // O RequireAuth deveria ter deixado renderizar o Dashboard (não /login).
    expect(auth.container.textContent).not.toContain('(login)') // sanity — nunca veio do Login
    expect(auth.container.querySelector('.layout-container')).not.toBeNull()
    expect(refreshCalls).toBe(1)
    auth.unmount()
  })

  it('F5 sem refresh token: RequireAuth manda para /login (sem loop)', async () => {
    semearCsrf()
    let refreshCalls = 0
    const auth = await montarAppComBootstrap('/', [
      http.post('/api/token/refresh/', () => {
        refreshCalls += 1
        return new HttpResponse(null, { status: 401 })
      }),
    ])

    expect(auth.container.textContent).not.toBeNull()
    // RequireAuth manda ao /login: a página de login renderizou, não o
    // Dashboard (layout-container é o layout autenticado).
    expect(auth.container.querySelector('.auth-wrapper')).not.toBeNull()
    expect(refreshCalls).toBe(1)
    auth.unmount()
  })
})

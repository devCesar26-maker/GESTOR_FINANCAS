import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  clearAccessToken,
  getAccessToken,
  initAuth,
  setAccessToken,
} from '../api/client'

// ---------------------------------------------------------------------------
// AuthContext / AuthProvider
// ---------------------------------------------------------------------------
// Fonte da verdade do TOKEN é o api/client.js (access token em memória;
// refresh token num cookie httpOnly — NUNCA em localStorage). Este provider
// adiciona o ESTADO de autenticação para a UI:
//
//   * No mount dispara a restauração de sessão (silent refresh via
//     POST /api/token/refresh/ com cookies, dentro do client) enquanto
//     mantém `loading = true` — as rotas protegidas (RequireAuth) NÃO
//     redirecionam para /login enquanto a verificação está em curso.
//
//   * Sucesso: guarda o novo access token (memória + estado) e marca o
//     usuário como autenticado.
//   * Falha (401/403/sem cookie): limpa o estado e loading = false — o
//     guarda de rotas é quem decide o redirecionamento para /login.
// ---------------------------------------------------------------------------

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // loading = true enquanto o silent refresh do bootstrap está em curso:
  // o App não renderiza as rotas (nem o RequireAuth decide) antes do fim.
  const [loading, setLoading] = useState(true)
  const [autenticado, setAutenticado] = useState(() => Boolean(getAccessToken()))
  const [token, setToken] = useState(() => getAccessToken())

  const sincronizar = useCallback(() => {
    const atual = getAccessToken()
    setToken(atual)
    setAutenticado(Boolean(atual))
    return Boolean(atual)
  }, [])

  // Restauração de sessão na inicialização (mount do AuthProvider).
  // Single-flight no client: chamadas simultâneas (StrictMode monta duas
  // vezes em dev) compartilham a mesma promessa — só um POST acontece.
  useEffect(() => {
    let ativo = true
    initAuth().finally(() => {
      if (ativo) {
        sincronizar()
        setLoading(false)
      }
    })
    return () => {
      ativo = false
    }
  }, [sincronizar])

  // O interceptor de 401 do client chama limpiarSesion() ao falhar o refresh:
  // expõe os manipuladores para o app inteiro via contexto.
  const login = useCallback(
    (novoAccessToken) => {
      setAccessToken(novoAccessToken)
      sincronizar()
    },
    [sincronizar],
  )

  const logout = useCallback(() => {
    clearAccessToken()
    sincronizar()
  }, [sincronizar])

  const value = useMemo(
    () => ({ loading, autenticado, token, login, logout, sincronizar }),
    [loading, autenticado, token, login, logout, sincronizar],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const contexto = useContext(AuthContext)
  if (!contexto) {
    throw new Error('useAuth deve ser usado dentro de <AuthProvider>')
  }
  return contexto
}

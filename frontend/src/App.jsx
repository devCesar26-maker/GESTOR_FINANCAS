import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getAccessToken, initAuth } from './api/client'
import Clientes from './pages/Clientes'
import Dashboard from './pages/Dashboard'
import Faturas from './pages/Faturas'
import Login from './pages/Login'
import Registro from './pages/Registro'

// Bootstrap da autenticação: o silent refresh roda UMA vez no carregamento
// do app e decide se existe sessão (cookie httpOnly válido). As rotas só
// renderizam depois — sem isso RequireAuth redirecionaria para /login por
// que o token em memória ainda não foi reidratado.
export default function App() {
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    let ativo = true
    // Single-flight dentro do client: chamadas simultâneas (StrictMode
    // monta efeitos duas vezes em dev) compartilham a mesma promessa.
    initAuth().finally(() => {
      if (ativo) setAuthReady(true)
    })
    return () => {
      ativo = false
    }
  }, [])

  if (!authReady) return null

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/clientes"
        element={
          <RequireAuth>
            <Clientes />
          </RequireAuth>
        }
      />
      <Route
        path="/faturas"
        element={
          <RequireAuth>
            <Faturas />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function RequireAuth({ children }) {
  // Token vive APENAS em memória: recarregar a página o perde — o silent
  // refresh no bootstrap acima é quem reidrata a sessão (ou manda ao login).
  if (!getAccessToken()) return <Navigate to="/login" replace />
  return children
}

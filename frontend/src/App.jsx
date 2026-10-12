import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import Clientes from './pages/Clientes'
import Dashboard from './pages/Dashboard'
import EsqueceuSenha from './pages/EsqueceuSenha'
import Faturas from './pages/Faturas'
import Login from './pages/Login'
import RedefinirSenha from './pages/RedefinirSenha'
import Registro from './pages/Registro'

// Bootstrap da autenticação: o AuthProvider (ver auth/AuthContext.jsx)
// dispara no mount a restauração da sessão (silent refresh — POST
// /api/token/refresh/ com o cookie httpOnly) mantendo `loading = true`
// até decidir se existe sessão. As rotas SÓ renderizam depois — sem isso o
// RequireAuth redirecionaria para /login porque o token em memória ainda
// não teria sido reidratado.
export default function App() {
  const { loading } = useAuth()

  // Durante a verificação inicial: não renderiza rota nenhuma (é o
  // equivalente a um splash — evita redirect precoco para /login em F5).
  if (loading) return null

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />
      {/* Fluxo de recuperação de senha (links do e-mail caem aqui). */}
      <Route path="/esqueceu-senha" element={<EsqueceuSenha />} />
      <Route path="/redefinir-senha/:uid/:token" element={<RedefinirSenha />} />
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
  // Estado do AuthContext, SINCRONIZADO com o client (o token vive APENAS em
  // memória: recarregar a página o perde — o silent refresh do bootstrap é
  // quem reidrata a sessão, ou manda ao login).
  const { autenticado } = useAuth()
  if (!autenticado) return <Navigate to="/login" replace />
  return children
}

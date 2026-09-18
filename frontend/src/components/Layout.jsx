import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import api, { clearAccessToken } from '../api/client'
import ConfirmDialog from './ConfirmDialog'

export default function Layout({ children }) {
  const navigate = useNavigate()
  // Modal de confirmação: a limpeza de tokens/sessão e o redirect para o
  // login só acontecem após "Confirmar Saída" (não no clique em "Sair").
  const [confirmandoSaida, setConfirmandoSaida] = useState(false)
  const [saindo, setSaindo] = useState(false)

  const confirmarSaida = async () => {
    setSaindo(true)
    // Avisa o backend para limpar o cookie httpOnly do refresh token;
    // depois limpa o access token local e volta ao login. Se a chamada
    // falhar (ex: sessão já morta), o logout local segue do mesmo jeito.
    try {
      await api.post('/token/logout/')
    } catch {
      /* noop */
    }
    clearAccessToken()
    setConfirmandoSaida(false)
    setSaindo(false)
    navigate('/login')
  }

  return (
    <div className="app-container">
      <header className="navbar">
        <Link to="/" className="brand">
          <div className="brand-icon">F</div>
          <span>FinFlow</span>
        </Link>
        <nav className="nav-links">
          <NavLink to="/" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Dashboard
          </NavLink>
          <NavLink to="/clientes" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Clientes
          </NavLink>
          <NavLink to="/faturas" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Faturas
          </NavLink>
          <button onClick={() => setConfirmandoSaida(true)} className="btn-logout">
            Sair
          </button>
        </nav>
      </header>
      <main className="content-container">{children}</main>

      {confirmandoSaida && (
        <ConfirmDialog
          titulo="Sair do FinFlow"
          mensagem="Tem certeza de que deseja sair do FinFlow?"
          textoCancelar="Cancelar"
          textoConfirmar="Confirmar Saída"
          variante="btn-primary"
          processando={saindo}
          textoProcessando="Saindo..."
          aoConfirmar={confirmarSaida}
          aoCancelar={() => setConfirmandoSaida(false)}
        />
      )}
    </div>
  )
}

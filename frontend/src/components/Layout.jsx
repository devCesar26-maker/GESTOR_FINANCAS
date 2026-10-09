import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import api, { clearAccessToken } from '../api/client'
import ConfirmDialog from './ConfirmDialog'
import { FinFlowLogo } from './FinFlowLogo'

export default function Layout({ children }) {
  const navigate = useNavigate()
  const [confirmandoSaida, setConfirmandoSaida] = useState(false)
  const [saindo, setSaindo] = useState(false)

  const confirmarSaida = async () => {
    setSaindo(true)
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
    <div className="layout-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <Link to="/" className="brand" style={{ textDecoration: 'none' }}>
            <FinFlowLogo />
          </Link>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/clientes" className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            <span>Clientes</span>
          </NavLink>
          <NavLink to="/faturas" className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            <span>Faturas</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <button onClick={() => setConfirmandoSaida(true)} className="btn-logout">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            <span>Sair</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        <div className="content-container">
          {children}
        </div>
      </main>

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

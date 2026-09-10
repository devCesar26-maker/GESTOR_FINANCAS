import { Link, NavLink, useNavigate } from 'react-router-dom'

export default function Layout({ children }) {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('finflow_access')
    localStorage.removeItem('finflow_refresh')
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
          <button onClick={handleLogout} className="btn-logout">
            Sair
          </button>
        </nav>
      </header>
      <main className="content-container">{children}</main>
    </div>
  )
}

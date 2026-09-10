import { Navigate, Route, Routes } from 'react-router-dom'
import Clientes from './pages/Clientes'
import Dashboard from './pages/Dashboard'
import Faturas from './pages/Faturas'
import Login from './pages/Login'

function RequireAuth({ children }) {
  const token = localStorage.getItem('finflow_access')
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
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
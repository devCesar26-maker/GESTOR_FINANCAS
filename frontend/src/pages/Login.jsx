import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import api, { setAccessToken } from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()

  // Voltou do cadastro bem-sucedido: mostra aviso e preenche o e-mail.
  const contaCriada = location.state?.contaCriada
  const usuarioInicial = contaCriada ?? 'admin'

  const [username, setUsername] = useState(usuarioInicial)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await api.post('/token/', { username, password })
      // Access token SÓ em memória (nada em localStorage — anti-XSS); o
      // refresh token chega num cookie httpOnly setado pelo backend.
      setAccessToken(response.data.access)
      navigate('/')
    } catch (err) {
      console.error(err)
      setError('Credenciais inválidas. Verifique usuário e senha.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div className="brand-icon" style={{ margin: '0 auto 1rem auto', width: '48px', height: '48px', fontSize: '1.5rem' }}>
            F
          </div>
          <h2>Entrar no FinFlow</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Gestão Financeira para Pequenos Negócios
          </p>
        </div>

        {contaCriada && (
          <div
            className="alert-error"
            style={{
              background: 'rgba(16, 185, 129, 0.12)',
              borderColor: 'rgba(16, 185, 129, 0.45)',
              color: '#34d399',
            }}
          >
            Conta criada com sucesso para <strong>{contaCriada}</strong>. Entre com suas credenciais.
          </div>
        )}

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Usuário</label>
            <input
              type="text"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Nome de usuário"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Senha</label>
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Sua senha"
              required
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
            {loading ? 'Entrando...' : 'Entrar'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          Não tem uma conta? <Link to="/registro" style={{ fontWeight: 600 }}>Criar conta</Link>
        </p>
      </div>
    </div>
  )
}
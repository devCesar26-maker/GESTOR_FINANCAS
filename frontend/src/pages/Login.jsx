import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import api, { setAccessToken } from '../api/client'
import BotaoGoogle from '../components/BotaoGoogle'
import { FinFlowLogo } from '../components/FinFlowLogo'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()

  const contaCriada = location.state?.contaCriada
  const senhaRedefinida = location.state?.senhaRedefinida
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
    <div className="auth-wrapper">
      <div className="auth-sidebar">
        <div className="auth-sidebar-logo">
          <FinFlowLogo />
        </div>
        <h1 className="auth-sidebar-title">Gestão financeira simples e inteligente</h1>
        <p className="auth-sidebar-desc">
          Monitore o fluxo de caixa, controle faturas e gerencie seus clientes em um painel integrado.
        </p>
        <div className="auth-features" style={{ marginTop: '2.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="auth-feature">
            <div className="auth-feature-dot" />
            <span>Relatórios financeiros detalhados (DRE & Fluxo de Caixa)</span>
          </div>
          <div className="auth-feature">
            <div className="auth-feature-dot" />
            <span>Gestão completa de faturas a pagar e receber</span>
          </div>
          <div className="auth-feature">
            <div className="auth-feature-dot" />
            <span>Notificações via WhatsApp ativas para seus clientes</span>
          </div>
        </div>
      </div>

      <div className="auth-main">
        <div className="auth-form-box">
          <h2 className="auth-form-title">Entrar no FinFlow</h2>
          <p className="auth-form-sub">Acesse sua conta para continuar</p>

          {contaCriada && (
            <div
              className="alert-error"
              style={{
                background: 'var(--accent-success-bg)',
                borderColor: 'var(--accent-success-border)',
                color: 'var(--accent-success)',
              }}
            >
              Conta criada com sucesso para <strong>{contaCriada}</strong>. Entre com suas credenciais.
            </div>
          )}

          {senhaRedefinida && (
            <div
              className="alert-error"
              style={{
                background: 'var(--accent-success-bg)',
                borderColor: 'var(--accent-success-border)',
                color: 'var(--accent-success)',
              }}
            >
              Senha redefinida com sucesso. Entre com a nova senha.
            </div>
          )}

          {error && <div className="alert-error">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Usuário ou e-mail</label>
              <input
                type="text"
                className="form-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="E-mail ou nome de usuário"
                autoComplete="username"
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

          <p style={{ textAlign: 'center', marginTop: '0.875rem', fontSize: '0.875rem' }}>
            <Link to="/esqueceu-senha" style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Esqueceu a senha?</Link>
          </p>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', margin: '1.25rem 0' }}>
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>ou</span>
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
          </div>

          <BotaoGoogle texto="Entrar com Google" />

          <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            Não tem uma conta? <Link to="/registro" style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Criar conta</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
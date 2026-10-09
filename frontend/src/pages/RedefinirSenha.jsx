import { useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'

const REGRAS_SENHA = [
  { rotulo: 'Pelo menos 8 caracteres', ok: (s) => s.length >= 8 },
  { rotulo: 'Uma letra maiúscula (A–Z)', ok: (s) => /[A-Z]/.test(s) },
  { rotulo: 'Uma letra minúscula (a–z)', ok: (s) => /[a-z]/.test(s) },
  { rotulo: 'Um número (0–9)', ok: (s) => /\d/.test(s) },
  { rotulo: 'Um caractere especial (ex: !@#$%)', ok: (s) => /[^A-Za-z0-9]/.test(s) },
]

export default function RedefinirSenha() {
  const { uid, token } = useParams()
  const navigate = useNavigate()

  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const validar = () => {
    const errs = {}
    if (!senha) {
      errs.senha = 'Informe a nova senha.'
    } else if (REGRAS_SENHA.some((r) => !r.ok(senha))) {
      errs.senha = 'A senha não cumpre todos os requisitos de segurança abaixo.'
    }
    if (confirmacao !== senha) errs.confirmacao = 'As senhas não coincidem.'
    return errs
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    const errs = validar()
    setErrors(errs)
    if (Object.keys(errs).length > 0) return

    setLoading(true)
    try {
      await api.post('/auth/password/reset/confirm/', {
        uid,
        token,
        new_password: senha,
      })
      navigate('/login', {
        state: { senhaRedefinida: true },
      })
    } catch (err) {
      console.error(err)
      setError(
        err.response?.data?.detail ??
          err.response?.data?.new_password?.[0] ??
          'Não foi possível redefinir a senha. Solicite um novo link.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrapper">
      <div className="auth-sidebar">
        <div className="auth-sidebar-logo">
          <div className="brand-icon">F</div>
          <span className="brand-name" style={{ color: '#fff', fontSize: '1.25rem', fontWeight: 700 }}>FinFlow</span>
        </div>
        <h1 className="auth-sidebar-title">Segurança em Primeiro Lugar</h1>
        <p className="auth-sidebar-desc">
          Defina uma nova senha forte para manter sua conta e dados financeiros protegidos.
        </p>
      </div>

      <div className="auth-main">
        <div className="auth-form-box">
          <h2 className="auth-form-title">Criar nova senha</h2>
          <p className="auth-form-sub">Escolha uma nova senha para sua conta</p>

          {error && <div className="alert-error">{error}</div>}

          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="nova-senha">Nova senha</label>
              <input
                id="nova-senha"
                type="password"
                className="form-input"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                placeholder="Sua nova senha forte"
                autoComplete="new-password"
              />
              {errors.senha && <small style={{ color: 'var(--accent-danger)' }}>{errors.senha}</small>}
              <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.8rem' }}>
                {REGRAS_SENHA.map((regra) => {
                  const satisfeita = regra.ok(senha)
                  return (
                    <li
                      key={regra.rotulo}
                      style={{
                        color: satisfeita ? 'var(--accent-success)' : 'var(--text-muted)',
                        marginBottom: '0.15rem',
                      }}
                    >
                      {satisfeita ? '✓' : '○'} {regra.rotulo}
                    </li>
                  )
                })}
              </ul>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="confirmar-nova-senha">Confirmar nova senha</label>
              <input
                id="confirmar-nova-senha"
                type="password"
                className="form-input"
                value={confirmacao}
                onChange={(e) => setConfirmacao(e.target.value)}
                placeholder="Repita a nova senha"
                autoComplete="new-password"
              />
              {errors.confirmacao && (
                <small style={{ color: 'var(--accent-danger)' }}>{errors.confirmacao}</small>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
              disabled={loading}
            >
              {loading ? 'Redefinindo...' : 'Redefinir senha'}
            </button>
          </form>

          <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            <Link to="/esqueceu-senha" style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Solicitar novo link</Link>
            {' • '}
            <Link to="/login" style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Voltar ao login</Link>
          </p>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { FinFlowLogo } from '../components/FinFlowLogo'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function EsqueceuSenha() {
  const [email, setEmail] = useState('')
  const [enviado, setEnviado] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    const emailTrim = email.trim()
    if (!EMAIL_RE.test(emailTrim)) {
      setError('Informe um e-mail válido.')
      return
    }

    setLoading(true)
    try {
      await api.post('/auth/password/reset/', { email: emailTrim })
      setEnviado(true)
    } catch (err) {
      console.error(err)
      setError(
        err.response?.data?.email?.[0] ??
          'Não foi possível enviar agora. Tente novamente em instantes.',
      )
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
        <h1 className="auth-sidebar-title">Recuperação de Acesso</h1>
        <p className="auth-sidebar-desc">
          Enviaremos as instruções necessárias para você redefinir sua senha com toda segurança.
        </p>
      </div>

      <div className="auth-main">
        <div className="auth-form-box">
          <h2 className="auth-form-title">Recuperar senha</h2>
          <p className="auth-form-sub">Recupere o acesso à sua conta FinFlow</p>

          {enviado ? (
            <>
              <div
                className="alert-error"
                style={{
                  background: 'var(--accent-success-bg)',
                  borderColor: 'var(--accent-success-border)',
                  color: 'var(--accent-success)',
                }}
              >
                Se este e-mail estiver cadastrado, você receberá um link de
                recuperação em instantes. Verifique também a caixa de spam.
              </div>
              <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                <Link to="/login" style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Voltar para o login</Link>
              </p>
            </>
          ) : (
            <>
              {error && <div className="alert-error">{error}</div>}

              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: 0, marginBottom: '1.25rem' }}>
                Informe o e-mail da sua conta e enviaremos um link para você criar
                uma nova senha. O link é válido por 1 hora.
              </p>

              <form onSubmit={handleSubmit} noValidate>
                <div className="form-group">
                  <label className="form-label" htmlFor="reset-email">E-mail</label>
                  <input
                    id="reset-email"
                    type="email"
                    className="form-input"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="voce@empresa.com.br"
                    autoComplete="email"
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: '100%', justifyContent: 'center' }}
                  disabled={loading}
                >
                  {loading ? 'Enviando...' : 'Enviar link de recuperação'}
                </button>
              </form>

              <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                Lembrou a senha? <Link to="/login" style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Entrar</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

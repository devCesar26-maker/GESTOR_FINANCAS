import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Página pública: solicita o link de recuperação de senha. O backend SEMPRE
// responde 200 (anti user-enumeration), então a mensagem exibida é a mesma
// exista ou não uma conta com o e-mail informado.
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
      await api.post('/auth/password-reset/', { email: emailTrim })
      setEnviado(true)
    } catch (err) {
      console.error(err)
      // Erros de campo do DRF (400) ou indisponibilidade do servidor.
      setError(
        err.response?.data?.email?.[0] ??
          'Não foi possível enviar agora. Tente novamente em instantes.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div
            className="brand-icon"
            style={{ margin: '0 auto 1rem auto', width: '48px', height: '48px', fontSize: '1.5rem' }}
          >
            F
          </div>
          <h2>Recuperar senha</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Gestão Financeira para Pequenos Negócios
          </p>
        </div>

        {enviado ? (
          <>
            <div
              className="alert-error"
              style={{
                background: 'rgba(16, 185, 129, 0.12)',
                borderColor: 'rgba(16, 185, 129, 0.45)',
                color: '#34d399',
              }}
            >
              Se este e-mail estiver cadastrado, você receberá um link de
              recuperação em instantes. Verifique também a caixa de spam.
            </div>
            <p style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              <Link to="/login" style={{ fontWeight: 600 }}>Voltar para o login</Link>
            </p>
          </>
        ) : (
          <>
            {error && <div className="alert-error">{error}</div>}

            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: 0 }}>
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

            <p style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              Lembrou a senha? <Link to="/login" style={{ fontWeight: 600 }}>Entrar</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}

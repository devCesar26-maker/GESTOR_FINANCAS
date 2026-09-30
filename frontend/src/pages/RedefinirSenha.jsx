import { useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Política de senha forte — deve espelhar SenhaForteValidator (backend).
const REGRAS_SENHA = [
  { rotulo: 'Pelo menos 8 caracteres', ok: (s) => s.length >= 8 },
  { rotulo: 'Uma letra maiúscula (A–Z)', ok: (s) => /[A-Z]/.test(s) },
  { rotulo: 'Uma letra minúscula (a–z)', ok: (s) => /[a-z]/.test(s) },
  { rotulo: 'Um número (0–9)', ok: (s) => /\d/.test(s) },
  { rotulo: 'Um caractere especial (ex: !@#$%)', ok: (s) => /[^A-Za-z0-9]/.test(s) },
]

// Página pública alcançada pelo link do e-mail: /redefinir-senha/:uid/:token.
// Envia uid+token+senha nova ao backend; os erros de token (400) são
// traduzidos em orientação para solicitar um novo link.
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
      await api.post('/auth/password-reset/confirm/', {
        uid,
        token,
        password: senha,
      })
      // Sucesso: volta ao login com aviso amigável (mesmo mecanismo do
      // "contaCriada" usado pelo Registro).
      navigate('/login', {
        state: { senhaRedefinida: true },
      })
    } catch (err) {
      console.error(err)
      setError(
        err.response?.data?.detail ??
          err.response?.data?.password?.[0] ??
          'Não foi possível redefinir a senha. Solicite um novo link.',
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
          <h2>Criar nova senha</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Gestão Financeira para Pequenos Negócios
          </p>
        </div>

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
                      color: satisfeita ? 'var(--accent-success, #34d399)' : 'var(--text-muted)',
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

        <p style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          <Link to="/esqueceu-senha" style={{ fontWeight: 600 }}>Solicitar novo link</Link>
          {' • '}
          <Link to="/login" style={{ fontWeight: 600 }}>Voltar ao login</Link>
        </p>
      </div>
    </div>
  )
}

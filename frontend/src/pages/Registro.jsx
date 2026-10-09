import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import BotaoGoogle from '../components/BotaoGoogle'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const REGRAS_SENHA = [
  { rotulo: 'Pelo menos 8 caracteres', ok: (s) => s.length >= 8 },
  { rotulo: 'Uma letra maiúscula (A–Z)', ok: (s) => /[A-Z]/.test(s) },
  { rotulo: 'Uma letra minúscula (a–z)', ok: (s) => /[a-z]/.test(s) },
  { rotulo: 'Um número (0–9)', ok: (s) => /\d/.test(s) },
  { rotulo: 'Um caractere especial (ex: !@#$%)', ok: (s) => /[^A-Za-z0-9]/.test(s) },
]

function traduzirErroBackend(data) {
  if (!data) return 'Não foi possível criar a conta. Tente novamente.'
  if (typeof data === 'string') return data
  if (data.detail) return data.detail

  const partes = []
  for (const [campo, valor] of Object.entries(data)) {
    const msgs = Array.isArray(valor) ? valor.join(' ') : String(valor)
    const rotulo = { email: 'E-mail', password: 'Senha', nome: 'Nome' }[campo] ?? campo
    partes.push(`${rotulo}: ${msgs}`)
  }
  return partes.join(' • ') || 'Não foi possível criar a conta. Tente novamente.'
}

export default function Registro() {
  const [form, setForm] = useState({ nome: '', email: '', senha: '', confirmacao: '' })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const set = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }))

  const validar = () => {
    const errs = {}
    if (!form.nome.trim()) errs.nome = 'Informe seu nome.'
    if (!form.email.trim()) errs.email = 'Informe seu e-mail.'
    else if (!EMAIL_RE.test(form.email.trim())) errs.email = 'E-mail inválido.'
    if (!form.senha.length) {
      errs.senha = 'Informe uma senha.'
    } else if (REGRAS_SENHA.some((r) => !r.ok(form.senha))) {
      errs.senha = 'A senha não cumpre todos os requisitos de segurança abaixo.'
    }
    if (form.confirmacao !== form.senha) errs.confirmacao = 'As senhas não coincidem.'
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
      await api.post('/auth/registro/', {
        nome: form.nome.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.senha,
      })
      navigate('/login', { state: { contaCriada: form.email.trim().toLowerCase() } })
    } catch (err) {
      setError(traduzirErroBackend(err.response?.data))
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
        <h1 className="auth-sidebar-title">Comece a gerenciar seu negócio hoje</h1>
        <p className="auth-sidebar-desc">
          Crie sua conta em menos de 1 minuto e tenha controle financeiro total da sua empresa.
        </p>
        <div className="auth-features" style={{ marginTop: '2.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="auth-feature">
            <div className="auth-feature-dot" />
            <span>Sem necessidade de cartão de crédito</span>
          </div>
          <div className="auth-feature">
            <div className="auth-feature-dot" />
            <span>Acesso completo ao painel financeiro</span>
          </div>
          <div className="auth-feature">
            <div className="auth-feature-dot" />
            <span>Integração simples com Google Login</span>
          </div>
        </div>
      </div>

      <div className="auth-main">
        <div className="auth-form-box">
          <h2 className="auth-form-title">Criar conta no FinFlow</h2>
          <p className="auth-form-sub">Preencha os dados abaixo para se cadastrar</p>

          {error && <div className="alert-error">{error}</div>}

          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="reg-nome">Nome</label>
              <input
                id="reg-nome"
                type="text"
                className="form-input"
                value={form.nome}
                onChange={set('nome')}
                placeholder="Seu nome completo"
              />
              {errors.nome && <small style={{ color: 'var(--accent-danger)' }}>{errors.nome}</small>}
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-email">E-mail</label>
              <input
                id="reg-email"
                type="email"
                className="form-input"
                value={form.email}
                onChange={set('email')}
                placeholder="voce@empresa.com.br"
                autoComplete="email"
              />
              {errors.email && <small style={{ color: 'var(--accent-danger)' }}>{errors.email}</small>}
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-senha">Senha</label>
              <input
                id="reg-senha"
                type="password"
                className="form-input"
                value={form.senha}
                onChange={set('senha')}
                placeholder="Sua senha forte"
                autoComplete="new-password"
              />
              {errors.senha && <small style={{ color: 'var(--accent-danger)' }}>{errors.senha}</small>}
              <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.8rem' }}>
                {REGRAS_SENHA.map((regra) => {
                  const satisfeita = regra.ok(form.senha)
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
              <label className="form-label" htmlFor="reg-confirmacao">Confirmar senha</label>
              <input
                id="reg-confirmacao"
                type="password"
                className="form-input"
                value={form.confirmacao}
                onChange={set('confirmacao')}
                placeholder="Repita a senha"
                autoComplete="new-password"
              />
              {errors.confirmacao && <small style={{ color: 'var(--accent-danger)' }}>{errors.confirmacao}</small>}
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
              {loading ? 'Criando conta...' : 'Criar conta'}
            </button>
          </form>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', margin: '1.25rem 0' }}>
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>ou</span>
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
          </div>

          <BotaoGoogle texto="Cadastrar com Google" />

          <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            Já tem uma conta? <Link to="/login" style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Entrar</Link>
          </p>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import api from '../api/client'
import Layout from '../components/Layout'
import ConfirmDialog from '../components/ConfirmDialog'

export default function Clientes() {
  const [clientes, setClientes] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [pageError, setPageError] = useState('')
  const [modalError, setModalError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Modal de confirmação de exclusão (substitui window.confirm nativo).
  const [clienteParaExcluir, setClienteParaExcluir] = useState(null)
  const [excluindo, setExcluindo] = useState(false)

  // Erros de validação inline, por campo (exibidos sob cada input).
  const [fieldErrors, setFieldErrors] = useState({})

  const [formData, setFormData] = useState({
    nome: '',
    papel: 'cliente',
    tipo_pessoa: 'pf',
    documento: '',
    email: '',
    telefone: '',
    notificacoes_ativas: true,
  })

  useEffect(() => {
    fetchClientes()
  }, [])

  const fetchClientes = async () => {
    try {
      setLoading(true)
      const res = await api.get('/clientes/')
      setClientes(res.data.results || res.data)
    } catch (err) {
      console.error(err)
      setPageError('Erro ao carregar lista de clientes.')
    } finally {
      setLoading(false)
    }
  }

  // -----------------------------------------------------------------------
  // Validação inline (antes do submit) — mensagens legíveis por campo.
  // Regras de negócio: documento e e-mail OBRIGATÓRIOS; telefone opcional.
  // -----------------------------------------------------------------------
  const validarFormulario = () => {
    const erros = {}

    if (!formData.nome.trim()) {
      erros.nome = 'O nome é obrigatório.'
    }

    if (!formData.documento.trim()) {
      erros.documento =
        formData.tipo_pessoa === 'pf'
          ? 'O CPF é obrigatório.'
          : 'O CNPJ é obrigatório.'
    } else if (formData.tipo_pessoa === 'pf') {
      const digitos = formData.documento.replace(/\D/g, '')
      if (digitos.length !== 11) {
        erros.documento = 'CPF inválido: informe os 11 dígitos.'
      }
    } else if (formData.tipo_pessoa === 'pj') {
      const digitos = formData.documento.replace(/\D/g, '')
      if (digitos.length !== 14) {
        erros.documento = 'CNPJ inválido: informe os 14 dígitos.'
      }
    }

    if (!formData.email.trim()) {
      erros.email = 'O e-mail é obrigatório.'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      erros.email = 'Informe um e-mail válido (ex.: nome@empresa.com).'
    }

    return erros
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setModalError('')

    const erros = validarFormulario()
    setFieldErrors(erros)
    if (Object.keys(erros).length > 0) return

    setSubmitting(true)
    try {
      await api.post('/clientes/', formData)
      setShowModal(false)
      setFormData({ nome: '', papel: 'cliente', tipo_pessoa: 'pf', documento: '', email: '', telefone: '', notificacoes_ativas: true })
      fetchClientes()
    } catch (err) {
      console.error(err)
      const data = err.response?.data
      let msg = 'Erro ao cadastrar cliente.'

      if (data && typeof data === 'object') {
        const errorMessages = []
        for (const [key, value] of Object.entries(data)) {
          const valStr = Array.isArray(value) ? value.join(', ') : String(value)
          errorMessages.push(`${key}: ${valStr}`)
        }
        if (errorMessages.length > 0) {
          msg = errorMessages.join(' | ')
        }
      }
      setModalError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!clienteParaExcluir) return
    setExcluindo(true)
    setPageError('')
    try {
      await api.delete(`/clientes/${clienteParaExcluir.id}/`)
      setClienteParaExcluir(null)
      fetchClientes()
    } catch (err) {
      console.error(err)
      const msg = err.response?.data?.detail || 'Não foi possível remover o cliente.'
      setPageError(msg)
      setClienteParaExcluir(null)
    } finally {
      setExcluindo(false)
    }
  }

  const estiloErroCampo = { color: 'var(--accent-danger)', fontSize: '0.8rem', marginTop: '0.25rem' }

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Clientes e Fornecedores</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Gestão de cadastros da sua empresa</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setModalError(''); setFieldErrors({}); setShowModal(true); }}>
          + Novo Cadastro
        </button>
      </div>

      {pageError && <div className="alert-error" style={{ marginBottom: '1rem' }}>{pageError}</div>}

      <div className="card-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Papel</th>
              <th>Tipo</th>
              <th>Documento</th>
              <th>Contato</th>
              <th>Lembretes</th>
              <th style={{ textAlign: 'right' }}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Carregando...</td>
              </tr>
            ) : clientes.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Nenhum cliente cadastrado.</td>
              </tr>
            ) : (
              clientes.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600 }}>{c.nome}</td>
                  <td>
                    <span className={`badge ${c.papel === 'cliente' ? 'badge-paga' : 'badge-pendente'}`}>
                      {c.papel}
                    </span>
                  </td>
                  <td>{c.tipo_pessoa === 'pf' ? 'Pessoa Física' : 'Pessoa Jurídica'}</td>
                  <td>{c.documento || '—'}</td>
                  <td>{c.email || c.telefone || '—'}</td>
                  <td>
                    {c.notificacoes_ativas !== false
                      ? <span className="badge badge-paga">lembretes ✓</span>
                      : <span className="badge badge-pendente">sem lembretes</span>}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn-danger btn-sm" onClick={() => setClienteParaExcluir(c)}>
                      Excluir
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {clienteParaExcluir && (
        <ConfirmDialog
          titulo="Excluir cliente"
          mensagem={`Tem certeza que deseja excluir "${clienteParaExcluir.nome}"? Esta ação não pode ser desfeita. Se o cliente tiver faturas vinculadas, a exclusão será bloqueada pelo sistema.`}
          textoConfirmar="Excluir definitivamente"
          aoConfirmar={handleDelete}
          aoCancelar={() => setClienteParaExcluir(null)}
          processando={excluindo}
        />
      )}

      {showModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3 className="modal-title">Novo Cadastro</h3>
              <button className="btn-logout" onClick={() => setShowModal(false)}>✕</button>
            </div>

            {modalError && (
              <div className="alert-error" style={{ marginBottom: '1.25rem' }}>
                {modalError}
              </div>
            )}

            <form onSubmit={handleCreate} noValidate>
              <div className="form-group">
                <label className="form-label">Nome Completo / Razão Social *</label>
                <input
                  type="text"
                  className="form-input"
                  required
                  value={formData.nome}
                  onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                />
                {fieldErrors.nome && <div style={estiloErroCampo}>{fieldErrors.nome}</div>}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Papel</label>
                  <select
                    className="form-select"
                    value={formData.papel}
                    onChange={(e) => setFormData({ ...formData, papel: e.target.value })}
                  >
                    <option value="cliente">Cliente</option>
                    <option value="fornecedor">Fornecedor</option>
                    <option value="ambos">Ambos</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Tipo de Pessoa</label>
                  <select
                    className="form-select"
                    value={formData.tipo_pessoa}
                    onChange={(e) => {
                      setFormData({ ...formData, tipo_pessoa: e.target.value })
                      setFieldErrors((prev) => ({ ...prev, documento: undefined }))
                    }}
                  >
                    <option value="pf">Física (PF)</option>
                    <option value="pj">Jurídica (PJ)</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Documento (CPF / CNPJ) *</label>
                <input
                  type="text"
                  className="form-input"
                  required
                  placeholder={formData.tipo_pessoa === 'pf' ? 'Ex: 123.456.789-09' : 'Ex: 34.357.386/0001-05'}
                  value={formData.documento}
                  onChange={(e) => setFormData({ ...formData, documento: e.target.value })}
                />
                {fieldErrors.documento && <div style={estiloErroCampo}>{fieldErrors.documento}</div>}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Email *</label>
                  <input
                    type="email"
                    className="form-input"
                    required
                    placeholder="ex.: contato@empresa.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                  {fieldErrors.email && <div style={estiloErroCampo}>{fieldErrors.email}</div>}
                </div>
                <div className="form-group">
                  <label className="form-label">Telefone</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Opcional"
                    value={formData.telefone}
                    onChange={(e) => setFormData({ ...formData, telefone: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={formData.notificacoes_ativas}
                    onChange={(e) => setFormData({ ...formData, notificacoes_ativas: e.target.checked })}
                  />
                  Enviar lembretes automáticos de vencimento a este cliente
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="button" className="btn btn-logout" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Salvando...' : 'Salvar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  )
}

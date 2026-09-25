import { useEffect, useState } from 'react'
import api from '../api/client'
import Layout from '../components/Layout'
import ConfirmDialog from '../components/ConfirmDialog'
import { montarLinkWhatsApp } from '../utils/whatsapp'
import { mascararTelefone } from '../utils/telefone'

// Botão "Conversar no WhatsApp" da linha do cliente.
// - Com telefone válido: abre https://wa.me/{numero}?text={msg} em nova aba.
// - Sem telefone (vazio ou só e-mail): desabilitado com tooltip explicativa.
function BotaoWhatsApp({ cliente }) {
  const link = montarLinkWhatsApp(cliente.nome, cliente.telefone)

  if (link) {
    return (
      <a
        className="btn btn-success btn-sm"
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        title="Conversar no WhatsApp"
        style={{ textDecoration: 'none' }}
      >
        💬
      </a>
    )
  }

  return (
    <button
      className="btn btn-success btn-sm"
      disabled
      title={
        cliente.telefone
          ? 'Telefone inválido para WhatsApp (use DDD + número, ex.: 11 98765-4321)'
          : 'Telefone não informado'
      }
    >
      💬
    </button>
  )
}

// Badge do campo Papel na listagem.
// - cliente: verde (mesma cor de status positivo)
// - fornecedor: laranja
// - ambos: entidade que é cliente E fornecedor do mesmo gestor — badge
//   neutro com os dois pontos de cor e rótulo explícito "Cliente/Fornecedor".
export function BadgePapel({ papel }) {
  if (papel === 'ambos') {
    return (
      <span className="badge badge-papel badge-ambos">
        <span className="papel-dot papel-dot-verde"></span>
        <span className="papel-dot papel-dot-laranja"></span>
        Cliente/Fornecedor
      </span>
    )
  }
  if (papel === 'fornecedor') {
    return <span className="badge badge-papel badge-pendente">Fornecedor</span>
  }
  return <span className="badge badge-papel badge-paga">Cliente</span>
}

const FORMULARIO_VAZIO = {
  nome: '',
  papel: 'cliente',
  tipo_pessoa: 'pf',
  documento: '',
  email: '',
  telefone: '',
  notificacoes_ativas: true,
}

export default function Clientes() {
  const [clientes, setClientes] = useState([])
  const [busca, setBusca] = useState('')
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [pageError, setPageError] = useState('')
  const [modalError, setModalError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Modal de confirmação de exclusão (substitui window.confirm nativo).
  const [clienteParaExcluir, setClienteParaExcluir] = useState(null)
  const [excluindo, setExcluindo] = useState(false)

  // Edição: cliente em edição no modal (null = modo criação).
  const [clienteEditando, setClienteEditando] = useState(null)

  // Modal de detalhes completos do cliente (oculta ações poluidas da tabela).
  const [clienteDetalhes, setClienteDetalhes] = useState(null)

  // Erros de validação inline, por campo (exibidos sob cada input).
  const [fieldErrors, setFieldErrors] = useState({})

  const [formData, setFormData] = useState(FORMULARIO_VAZIO)

  useEffect(() => {
    fetchClientes()
  }, [])

  const fetchClientes = async (termo = busca) => {
    try {
      setLoading(true)
      // Busca textual server-side (ORM no backend): nome, CPF/CNPJ, e-mail e telefone.
      const params = termo.trim() ? { search: termo.trim() } : {}
      const res = await api.get('/clientes/', { params })
      setClientes(res.data.results || res.data)
    } catch (err) {
      console.error(err)
      setPageError('Erro ao carregar lista de clientes.')
    } finally {
      setLoading(false)
    }
  }

  // Debounce simples da busca textual (evita request a cada tecla).
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchClientes(busca)
    }, 350)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busca])

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
    } else if (
      clienteEditando &&
      formData.documento === clienteEditando.documento &&
      formData.documento.includes('*')
    ) {
      // Documento mascarado da listagem (LGPD), intacto: sem validação local.
      // O backend preserva o valor original salvo na base.
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

  const abrirModalNovo = () => {
    setClienteEditando(null)
    setFormData(FORMULARIO_VAZIO)
    setModalError('')
    setFieldErrors({})
    setShowModal(true)
  }

  const abrirModalEdicao = (cliente) => {
    // Modal PRÉ-PREENCHIDO com os dados atuais do registro.
    setClienteEditando(cliente)
    setFormData({
      nome: cliente.nome || '',
      papel: cliente.papel || 'cliente',
      tipo_pessoa: cliente.tipo_pessoa || 'pf',
      documento: cliente.documento || '',
      email: cliente.email || '',
      telefone: cliente.telefone || '',
      notificacoes_ativas: cliente.notificacoes_ativas !== false,
    })
    setModalError('')
    setFieldErrors({})
    setShowModal(true)
  }

  const handleSalvar = async (e) => {
    e.preventDefault()
    setModalError('')

    const erros = validarFormulario()
    setFieldErrors(erros)
    if (Object.keys(erros).length > 0) return

    setSubmitting(true)
    try {
      if (clienteEditando) {
        // Edição: PUT /api/clientes/{id}/ com payload completo. Se o documento
        // permaneceu como veio da listagem (mascarado por LGPD), segue no
        // payload: o serializer do backend detecta o "*" e preserva o valor
        // original salvo na base, sem erro de validação.
        await api.put(`/clientes/${clienteEditando.id}/`, formData)
      } else {
        await api.post('/clientes/', formData)
      }
      setShowModal(false)
      setClienteEditando(null)
      setFormData(FORMULARIO_VAZIO)
      fetchClientes()
    } catch (err) {
      console.error(err)
      const data = err.response?.data
      let msg = clienteEditando ? 'Erro ao salvar alterações.' : 'Erro ao cadastrar cliente.'

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
        <button className="btn btn-primary" onClick={abrirModalNovo}>
          + Novo Cadastro
        </button>
      </div>

      {pageError && <div className="alert-error" style={{ marginBottom: '1rem' }}>{pageError}</div>}

      <div className="card-table" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="search"
            className="form-input"
            style={{ maxWidth: 420 }}
            placeholder="Buscar por nome, CPF/CNPJ ou e-mail..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            aria-label="Buscar clientes"
          />
          {busca && (
            <button className="btn btn-logout btn-sm" onClick={() => setBusca('')}>
              Limpar
            </button>
          )}
        </div>
      </div>

      <div className="card-table">
        {/* table-scroll: em telas estreitas a tabela rola na horizontal;
            abaixo de 768px o CSS transforma as linhas em cards. */}
        <div className="table-scroll">
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
                <td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                  {busca ? 'Nenhum cliente encontrado para a busca.' : 'Nenhum cliente cadastrado.'}
                </td>
              </tr>
            ) : (
              clientes.map((c) => (
                <tr key={c.id}>
                  <td data-label="Nome" style={{ fontWeight: 600 }}>{c.nome}</td>
                  <td data-label="Papel">
                    <BadgePapel papel={c.papel} />
                  </td>
                  <td data-label="Tipo">{c.tipo_pessoa === 'pf' ? 'Pessoa Física' : 'Pessoa Jurídica'}</td>
                  <td data-label="Documento" style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{c.documento || ''}</td>
                  <td data-label="Contato" style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{c.email || c.telefone || ''}</td>
                  <td data-label="Lembretes">
                    {c.notificacoes_ativas !== false
                      ? <span className="indicator-bell" title="Lembretes automáticos ativos">🔔</span>
                      : <span className="indicator-bell" title="Sem lembretes" style={{ opacity: 0.2 }}>🔕</span>}
                  </td>
                  <td data-label="Ações" style={{ textAlign: 'right' }}>
                    <div className="table-actions">
                      <BotaoWhatsApp cliente={c} />
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setClienteDetalhes(c)}
                        title="Ver detalhes do cadastro"
                      >
                        👁️ Detalhes
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>
      </div>

      {clienteDetalhes && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Detalhes do cliente">
          <div className="modal-card" style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 className="modal-title">Detalhes do Cadastro</h3>
              <button className="btn-logout" onClick={() => setClienteDetalhes(null)} aria-label="Fechar">✕</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '1.25rem', fontSize: '0.9rem' }}>
              <div style={{ gridColumn: '1 / -1' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Nome</span>
                <strong style={{ fontSize: '1.1rem' }}>{clienteDetalhes.nome}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Papel</span>
                <BadgePapel papel={clienteDetalhes.papel} />
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Tipo Pessoa</span>
                <span>{clienteDetalhes.tipo_pessoa === 'pf' ? 'Pessoa Física' : 'Pessoa Jurídica'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>CPF / CNPJ</span>
                <span>{clienteDetalhes.documento || 'Não informado'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Lembretes Automáticos</span>
                <span>{clienteDetalhes.notificacoes_ativas !== false ? '🔔 Ativos' : '🔕 Desativados'}</span>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>E-mail</span>
                <span>{clienteDetalhes.email || 'Não informado'}</span>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Telefone / WhatsApp</span>
                <span>{clienteDetalhes.telefone || 'Não informado'}</span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1.25rem' }}>
              <BotaoWhatsApp cliente={clienteDetalhes} />
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  const target = clienteDetalhes;
                  setClienteDetalhes(null);
                  abrirModalEdicao(target);
                }}
              >
                ✏️ Editar Cadastro
              </button>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => {
                  const target = clienteDetalhes;
                  setClienteDetalhes(null);
                  setClienteParaExcluir(target);
                }}
              >
                🗑️ Excluir
              </button>
              <button className="btn btn-logout btn-sm" onClick={() => setClienteDetalhes(null)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

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
              <h3 className="modal-title">
                {clienteEditando ? `Editar: ${clienteEditando.nome}` : 'Novo Cadastro'}
              </h3>
              <button className="btn-logout" onClick={() => setShowModal(false)}>✕</button>
            </div>

            {modalError && (
              <div className="alert-error" style={{ marginBottom: '1.25rem' }}>
                {modalError}
              </div>
            )}

            <form onSubmit={handleSalvar} noValidate>
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
                    placeholder="Opcional — ex.: (11) 98765-4321"
                    value={formData.telefone}
                    onChange={(e) =>
                      setFormData({ ...formData, telefone: mascararTelefone(e.target.value) })
                    }
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
                  {submitting ? 'Salvando...' : clienteEditando ? 'Salvar Alterações' : 'Salvar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  )
}

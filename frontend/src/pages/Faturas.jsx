import { useEffect, useState } from 'react'
import api from '../api/client'
import Layout from '../components/Layout'
import ConfirmDialog from '../components/ConfirmDialog'
import { montarLinkCobranca } from '../utils/whatsapp'

// Botão "Cobrar no WhatsApp" para faturas A RECEBER pendentes/vencidas.
// Abre wa.me com número do cliente e mensagem com número, valor e vencimento.
// Sem telefone válido no cadastro: botão desabilitado com tooltip.
function BotaoCobrancaWhatsApp({ fatura }) {
  const link = montarLinkCobranca(fatura)

  if (link) {
    return (
      <a
        className="btn btn-success btn-xs"
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        title="Cobrar no WhatsApp"
        style={{ textDecoration: 'none' }}
      >
        💬
      </a>
    )
  }

  return (
    <button
      className="btn btn-success btn-xs"
      disabled
      title={
        fatura.cliente_telefone
          ? 'Telefone do cliente inválido para WhatsApp (cadastre DDD + número)'
          : 'Telefone do cliente não informado'
      }
    >
      💬
    </button>
  )
}

const MAX_COMPROVANTE_BYTES = 5 * 1024 * 1024 // 5 MB (mesma regra do backend)
const TIPOS_COMPROVANTE = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']

const FORMULARIO_VAZIO = {
  numero: '',
  cliente: '',
  descricao: '',
  tipo: 'a_receber',
  valor: '',
  vencimento: '',
  categoria: '',
}

// Faturas editáveis: apenas pendentes ("A Receber" / "A Pagar"). Pagas,
// vencidas e canceladas são SOMENTE LEITURA (o backend reforça com 409).
const ehEditavel = (fatura) => fatura.status === 'pendente'

// Resolve a URL do comprovante: o backend agora devolve o caminho relativo
// "/media/..." (sem host), evitando hostnames internos do Docker (backend:8000).
// No dev, o caminho é servido pelo proxy do Vite para o backend; em produção,
// pelo mesmo domínio (Nginx). Se um dia vier uma URL absoluta, mantemos como está.
const urlComprovante = (url) =>
  !url || /^https?:\/\//i.test(url) ? url : `/media/${String(url).replace(/^\/+/, '').replace(/^media\//, '')}`

export default function Faturas() {
  const [faturas, setFaturas] = useState([])
  const [clientes, setClientes] = useState([])
  const [categorias, setCategorias] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [pageError, setPageError] = useState('')
  const [modalError, setModalError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Filtros avançados (aplicados server-side via django-filter/ORM).
  const [filtros, setFiltros] = useState({
    status: '',
    tipo: '',
    vencimento_apos: '',
    vencimento_ate: '',
    busca: '',
  })

  // Edição: fatura em edição no modal (null = modo criação).
  const [faturaEditando, setFaturaEditando] = useState(null)

  // Modal de detalhes completos da fatura (oculta ações poluidas da tabela).
  const [faturaDetalhes, setFaturaDetalhes] = useState(null)

  // Modal de confirmação de cancelamento (substitui window.confirm nativo).
  const [faturaParaCancelar, setFaturaParaCancelar] = useState(null)
  const [cancelando, setCancelando] = useState(false)

  // Modal de confirmação de exclusão.
  const [faturaParaExcluir, setFaturaParaExcluir] = useState(null)
  const [excluindo, setExcluindo] = useState(false)

  // Modal de pagamento com COMPROVANTE OBRIGATÓRIO.
  const [faturaParaPagar, setFaturaParaPagar] = useState(null)
  const [comprovante, setComprovante] = useState(null)
  const [pagamentoError, setPagamentoError] = useState('')
  const [pagando, setPagando] = useState(false)

  const [formData, setFormData] = useState(FORMULARIO_VAZIO)

  // Download de comprovante em andamento (botão 📎).
  const [baixandoComprovante, setBaixandoComprovante] = useState(false)

  // Abre o comprovante em nova aba COM AUTENTICAÇÃO: o JWT viaja no header
  // (nunca na URL) e a resposta vira um blob local. O backend só serve o
  // arquivo ao dono da fatura — 404 para qualquer outro usuário.
  async function abrirComprovante(fatura) {
    const url = urlComprovante(fatura.comprovante_url)
    if (!url) return
    setBaixandoComprovante(true)
    try {
      // baseURL vazia por chamada: /media/... NÃO deve receber o prefixo /api.
      const response = await api.get(url, { baseURL: '', responseType: 'blob' })
      const blobUrl = window.URL.createObjectURL(response.data)
      window.open(blobUrl, '_blank', 'noopener,noreferrer')
      // Libera a memória do blob depois que o navegador abre a aba.
      setTimeout(() => window.URL.revokeObjectURL(blobUrl), 30_000)
    } catch {
      setPageError('Não foi possível abrir o comprovante (arquivo indisponível ou sem permissão).')
    } finally {
      setBaixandoComprovante(false)
    }
  }

  useEffect(() => {
    fetchFaturas()
    fetchClientes()
    fetchCategorias()
  }, [])

  const fetchFaturas = async (params = filtros) => {
    try {
      setLoading(true)
      // Remove chaves vazias para não poluir a querystring.
      const query = Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== '' && v != null)
      )
      const res = await api.get('/faturas/', { params: query })
      setFaturas(res.data.results || res.data)
    } catch (err) {
      console.error(err)
      setPageError('Erro ao carregar faturas.')
    } finally {
      setLoading(false)
    }
  }

  const aplicarFiltros = (novos) => {
    const atualizados = { ...filtros, ...novos }
    setFiltros(atualizados)
    fetchFaturas(atualizados)
  }

  const limparFiltros = () => {
    const zerados = { status: '', tipo: '', vencimento_apos: '', vencimento_ate: '', busca: '' }
    setFiltros(zerados)
    fetchFaturas(zerados)
  }

  const fetchClientes = async () => {
    try {
      const res = await api.get('/clientes/')
      setClientes(res.data.results || res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const fetchCategorias = async () => {
    try {
      // A primeira listagem semeia o catálogo padrão no backend (idempotente).
      const res = await api.get('/categorias/')
      setCategorias(res.data.results || res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const abrirModalNovo = () => {
    setFaturaEditando(null)
    setFormData(FORMULARIO_VAZIO)
    setModalError('')
    setShowModal(true)
  }

  const abrirModalEdicao = (fatura) => {
    if (!ehEditavel(fatura)) return // defesa extra: pagas/vencidas não abrem edição
    setFaturaEditando(fatura)
    setFormData({
      numero: fatura.numero || '',
      cliente: String(fatura.cliente || ''),
      descricao: fatura.descricao || '',
      tipo: fatura.tipo || 'a_receber',
      valor: fatura.valor ?? '',
      vencimento: fatura.vencimento || '',
      categoria: fatura.categoria ? String(fatura.categoria) : '',
    })
    setModalError('')
    setShowModal(true)
  }

  const handleSalvar = async (e) => {
    e.preventDefault()
    setModalError('')
    setSubmitting(true)
    try {
      const payload = {
        ...formData,
        categoria: formData.categoria === '' ? null : formData.categoria,
      }
      if (faturaEditando) {
        // Edição: PUT /api/faturas/{id}/ — bloqueado no backend para faturas pagas.
        await api.put(`/faturas/${faturaEditando.id}/`, payload)
      } else {
        await api.post('/faturas/', payload)
      }
      setShowModal(false)
      setFaturaEditando(null)
      setFormData(FORMULARIO_VAZIO)
      fetchFaturas()
    } catch (err) {
      console.error(err)
      const data = err.response?.data
      let msg = faturaEditando ? 'Erro ao salvar alterações.' : 'Erro ao criar fatura.'

      if (data) {
        if (typeof data.detail === 'string') msg = data.detail
        else if (data.numero) msg = `Número: ${Array.isArray(data.numero) ? data.numero[0] : data.numero}`
        else if (data.non_field_errors) {
          msg = Array.isArray(data.non_field_errors) ? data.non_field_errors[0] : data.non_field_errors
        } else if (typeof data === 'object') {
          const parts = Object.entries(data).map(
            ([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`
          )
          if (parts.length > 0) msg = parts.join(' | ')
        }
      }
      setModalError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const abrirModalPagar = (fatura) => {
    setFaturaParaPagar(fatura)
    setComprovante(null)
    setPagamentoError('')
  }

  const validarComprovante = (arquivo) => {
    if (!arquivo) return 'O comprovante de pagamento é obrigatório.'
    if (arquivo.size > MAX_COMPROVANTE_BYTES) return 'O arquivo excede o tamanho máximo de 5 MB.'
    if (arquivo.type && !TIPOS_COMPROVANTE.includes(arquivo.type)) {
      return 'Tipo de arquivo não permitido. Envie um PDF, JPEG, PNG ou WEBP.'
    }
    return ''
  }

  const handleSelecionarComprovante = (e) => {
    const arquivo = e.target.files?.[0] || null
    setComprovante(arquivo)
    setPagamentoError(arquivo ? validarComprovante(arquivo) : '')
  }

  const handlePagar = async (e) => {
    e.preventDefault()
    if (!faturaParaPagar) return

    // Impede a submissão sem arquivo — o comprovante é OBRIGATÓRIO.
    const erro = validarComprovante(comprovante)
    if (erro) {
      setPagamentoError(erro)
      return
    }

    setPagando(true)
    setPagamentoError('')
    setPageError('')
    try {
      // Upload via multipart/form-data (FormData) — o backend espera o
      // campo "comprovante" em request.FILES.
      const payload = new FormData()
      payload.append('comprovante', comprovante)
      await api.post(`/faturas/${faturaParaPagar.id}/pagar/`, payload)
      setFaturaParaPagar(null)
      setComprovante(null)
      fetchFaturas()
    } catch (err) {
      console.error(err)
      const data = err.response?.data
      let msg = 'Não foi possível pagar a fatura.'
      if (data?.comprovante) {
        msg = Array.isArray(data.comprovante) ? data.comprovante[0] : String(data.comprovante)
      } else if (typeof data?.detail === 'string') {
        msg = data.detail
      }
      setPagamentoError(msg)
    } finally {
      setPagando(false)
    }
  }

  const handleCancelar = async () => {
    if (!faturaParaCancelar) return
    setCancelando(true)
    setPageError('')
    try {
      await api.post(`/faturas/${faturaParaCancelar.id}/cancelar/`)
      setFaturaParaCancelar(null)
      fetchFaturas()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Não foi possível cancelar a fatura.'
      setPageError(msg)
      setFaturaParaCancelar(null)
    } finally {
      setCancelando(false)
    }
  }

  const handleExcluir = async () => {
    if (!faturaParaExcluir) return
    setExcluindo(true)
    setPageError('')
    try {
      await api.delete(`/faturas/${faturaParaExcluir.id}/`)
      setFaturaParaExcluir(null)
      fetchFaturas()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Não foi possível excluir a fatura.'
      setPageError(msg)
      setFaturaParaExcluir(null)
    } finally {
      setExcluindo(false)
    }
  }

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0)
  }

  // Exportação do extrato de faturas (respeita os filtros ativos na tela).
  // Baixa autenticada via axios (blob) — o JWT nunca vai na URL.
  const exportarFaturas = async (formato) => {
    try {
      const query = Object.fromEntries(
        Object.entries({ ...filtros, formato }).filter(([, v]) => v !== '' && v != null)
      )
      const res = await api.get('/faturas/exportar/', {
        params: query,
        responseType: 'blob',
      })
      const nome = formato === 'pdf' ? 'faturas.pdf' : 'faturas.csv'
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', nome)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setPageError('')
    } catch (err) {
      console.error(err)
      setPageError(`Falha ao exportar ${nome}.`)
    }
  }

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Faturas & Contas</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Gestão de contas a pagar e a receber</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-logout btn-sm" onClick={() => exportarFaturas('csv')}>
            Exportar CSV
          </button>
          <button className="btn btn-logout btn-sm" onClick={() => exportarFaturas('pdf')}>
            Exportar PDF
          </button>
          <button className="btn btn-primary" onClick={abrirModalNovo}>
            + Nova Fatura
          </button>
        </div>
      </div>

      {pageError && <div className="alert-error" style={{ marginBottom: '1rem' }}>{pageError}</div>}

      {/* ------------------------------------------------ Filtros avançados */}
      <div className="card-table" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem' }}>
          <select
            className="form-select"
            value={filtros.status}
            onChange={(e) => aplicarFiltros({ status: e.target.value })}
            aria-label="Filtrar por status"
          >
            <option value="">Status: todos</option>
            <option value="pendente">Pendente</option>
            <option value="paga">Paga</option>
            <option value="vencida">Vencida</option>
            <option value="cancelada">Cancelada</option>
          </select>

          <select
            className="form-select"
            value={filtros.tipo}
            onChange={(e) => aplicarFiltros({ tipo: e.target.value })}
            aria-label="Filtrar por tipo"
          >
            <option value="">Tipo: todos</option>
            <option value="a_receber">Receber</option>
            <option value="a_pagar">Pagar</option>
          </select>

          <input
            type="date"
            className="form-input"
            value={filtros.vencimento_apos}
            onChange={(e) => aplicarFiltros({ vencimento_apos: e.target.value })}
            aria-label="Vencimento a partir de"
            title="Vencimento a partir de"
          />
          <input
            type="date"
            className="form-input"
            value={filtros.vencimento_ate}
            onChange={(e) => aplicarFiltros({ vencimento_ate: e.target.value })}
            aria-label="Vencimento até"
            title="Vencimento até"
          />
          <input
            type="search"
            className="form-input"
            placeholder="Buscar número/descrição..."
            value={filtros.busca}
            onChange={(e) => aplicarFiltros({ busca: e.target.value })}
            aria-label="Buscar faturas"
          />
          <button className="btn btn-logout" onClick={limparFiltros}>
            Limpar filtros
          </button>
        </div>
      </div>

      <div className="card-table">
        {/* table-scroll: em telas estreitas a tabela rola na horizontal em vez
            de cortar o último botão de ação na borda do card. Abaixo de 768px
            o CSS transforma as linhas em cards (ver styles.css). */}
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Número</th>
              <th>Cliente / Fornecedor</th>
              <th>Categoria</th>
              <th>Descrição</th>
              <th>Tipo</th>
              <th>Vencimento</th>
              <th>Valor</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="9" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Carregando faturas...</td>
              </tr>
            ) : faturas.length === 0 ? (
              <tr>
                <td colSpan="9" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Nenhuma fatura cadastrada.</td>
              </tr>
            ) : (
              faturas.map((f) => (
                <tr key={f.id}>
                  <td data-label="Número" style={{ fontWeight: 600 }}>{f.numero}</td>
                  <td data-label="Cliente/Fornecedor">{f.cliente_nome || f.cliente}</td>
                  <td data-label="Categoria" style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{f.categoria_nome || ''}</td>
                  <td data-label="Descrição" style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{f.descricao || ''}</td>
                  <td data-label="Tipo" style={{ minWidth: '90px' }}>
                    <span style={{ color: f.tipo === 'a_receber' ? 'var(--accent-success)' : 'var(--accent-danger)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      {f.tipo === 'a_receber' ? 'Receber' : 'Pagar'}
                    </span>
                  </td>
                  <td data-label="Vencimento">{f.vencimento}</td>
                  <td data-label="Valor" style={{ fontWeight: 700 }}>{formatCurrency(f.valor)}</td>
                  <td data-label="Status">
                    <span className={`badge badge-${f.status}`}>
                      {f.status}
                    </span>
                  </td>
                  {/* Ações compactas: .table-actions (flex wrap) substitui o
                      antigo estilo inline (inline não pode ser sobrescrito por
                      media queries). No desktop alinha à direita como antes;
                      no modo card (< 768px) quebra linha sem estourar. */}
                  <td data-label="Ações" style={{ textAlign: 'right' }}>
                    <div className="table-actions">
                      {f.tipo === 'a_receber' && (f.status === 'pendente' || f.status === 'vencida') && (
                        <BotaoCobrancaWhatsApp fatura={f} />
                      )}
                      {(f.status === 'pendente' || f.status === 'vencida') && (
                        <button
                          className="btn btn-success btn-xs"
                          onClick={() => abrirModalPagar(f)}
                        >
                          {f.tipo === 'a_pagar' ? 'Pagar' : 'Receber'}
                        </button>
                      )}
                      {f.status === 'paga' && f.comprovante_url && (
                        <button
                          className="btn btn-outline btn-xs"
                          onClick={() => abrirComprovante(f)}
                          disabled={baixandoComprovante}
                          title="Visualizar Comprovante de Pagamento"
                          aria-label="Visualizar Comprovante de Pagamento"
                        >
                          📎 Comprovante
                        </button>
                      )}
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={() => setFaturaDetalhes(f)}
                        title="Ver detalhes da fatura"
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

      {faturaDetalhes && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Detalhes da fatura">
          <div className="modal-card" style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <h3 className="modal-title">Detalhes da Fatura {faturaDetalhes.numero}</h3>
              <button className="btn-logout" onClick={() => setFaturaDetalhes(null)} aria-label="Fechar">✕</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '1.25rem', fontSize: '0.9rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Cliente / Fornecedor</span>
                <strong>{faturaDetalhes.cliente_nome || faturaDetalhes.cliente}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Categoria</span>
                <span>{faturaDetalhes.categoria_nome || 'Sem categoria'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Tipo</span>
                <span style={{ color: faturaDetalhes.tipo === 'a_receber' ? 'var(--accent-success)' : 'var(--accent-danger)', fontWeight: 600 }}>
                  {faturaDetalhes.tipo === 'a_receber' ? 'A Receber' : 'A Pagar'}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Valor</span>
                <strong style={{ fontSize: '1.05rem' }}>{formatCurrency(faturaDetalhes.valor)}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Vencimento</span>
                <span>{faturaDetalhes.vencimento}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'block' }}>Status</span>
                <span className={`badge badge-${faturaDetalhes.status}`}>{faturaDetalhes.status}</span>
              </div>
            </div>

            {faturaDetalhes.descricao && (
              <div style={{ background: 'var(--bg-input)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', marginBottom: '1.25rem', fontSize: '0.875rem' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block', marginBottom: '0.2rem' }}>Descrição</span>
                {faturaDetalhes.descricao}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              {faturaDetalhes.status === 'paga' && faturaDetalhes.comprovante_url && (
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => { abrirComprovante(faturaDetalhes); }}
                  disabled={baixandoComprovante}
                >
                  📎 Ver Comprovante
                </button>
              )}
              {ehEditavel(faturaDetalhes) && (
                <>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      const target = faturaDetalhes;
                      setFaturaDetalhes(null);
                      abrirModalEdicao(target);
                    }}
                  >
                    ✏️ Editar Fatura
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => {
                      const target = faturaDetalhes;
                      setFaturaDetalhes(null);
                      setFaturaParaCancelar(target);
                    }}
                  >
                    🚫 Cancelar Fatura
                  </button>
                </>
              )}
              <button className="btn btn-logout btn-sm" onClick={() => setFaturaDetalhes(null)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {faturaParaCancelar && (
        <ConfirmDialog
          titulo="Cancelar fatura"
          mensagem={`A fatura ${faturaParaCancelar.numero} ficará com status Cancelada permanentemente e não poderá ser reativada. Deseja continuar?`}
          textoConfirmar="Cancelar fatura"
          aoConfirmar={handleCancelar}
          aoCancelar={() => setFaturaParaCancelar(null)}
          processando={cancelando}
        />
      )}

      {faturaParaExcluir && (
        <ConfirmDialog
          titulo="Excluir fatura"
          mensagem={`Tem certeza que deseja excluir a fatura ${faturaParaExcluir.numero}? Esta ação não pode ser desfeita.`}
          textoConfirmar="Excluir definitivamente"
          aoConfirmar={handleExcluir}
          aoCancelar={() => setFaturaParaExcluir(null)}
          processando={excluindo}
        />
      )}

      {faturaParaPagar && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Registrar pagamento">
          <div className="modal-card" style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 className="modal-title">
                {faturaParaPagar.tipo === 'a_pagar' ? 'Pagar fatura' : 'Registrar recebimento'}
              </h3>
              <button
                className="btn-logout"
                onClick={() => setFaturaParaPagar(null)}
                disabled={pagando}
                aria-label="Fechar"
              >
                ✕
              </button>
            </div>

            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.6, marginBottom: '1rem' }}>
              Fatura <strong>{faturaParaPagar.numero}</strong> —{' '}
              {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(faturaParaPagar.valor)}
            </p>

            {pagamentoError && (
              <div className="alert-error" style={{ marginBottom: '1rem' }}>
                {pagamentoError}
              </div>
            )}

            <form onSubmit={handlePagar} noValidate>
              <div className="form-group">
                <label className="form-label" htmlFor="comprovante-input">
                  Comprovante de pagamento (obrigatório) *
                </label>
                <input
                  id="comprovante-input"
                  type="file"
                  className="form-input"
                  accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
                  required
                  onChange={handleSelecionarComprovante}
                  disabled={pagando}
                />
                <small style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                  Formatos aceitos: PDF, JPEG, PNG ou WEBP — até 5 MB.
                </small>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button
                  type="button"
                  className="btn btn-logout"
                  onClick={() => setFaturaParaPagar(null)}
                  disabled={pagando}
                >
                  Voltar
                </button>
                <button type="submit" className="btn btn-success" disabled={pagando}>
                  {pagando ? 'Registrando...' : 'Confirmar pagamento'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3 className="modal-title">
                {faturaEditando ? `Editar fatura ${faturaEditando.numero}` : 'Nova Fatura'}
              </h3>
              <button className="btn-logout" onClick={() => setShowModal(false)}>✕</button>
            </div>

            {modalError && (
              <div className="alert-error" style={{ marginBottom: '1.25rem' }}>
                {modalError}
              </div>
            )}

            <form onSubmit={handleSalvar}>
              <div className="form-group">
                <label className="form-label">Número da Fatura</label>
                <input
                  type="text"
                  className="form-input"
                  required
                  placeholder="Ex: FAT-2026-001"
                  value={formData.numero}
                  onChange={(e) => setFormData({ ...formData, numero: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Cliente / Fornecedor</label>
                <select
                  className="form-select"
                  required
                  value={formData.cliente}
                  onChange={(e) => setFormData({ ...formData, cliente: e.target.value })}
                >
                  <option value="">Selecione um cliente...</option>
                  {clientes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Descrição</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.descricao}
                  onChange={(e) => setFormData({ ...formData, descricao: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Categoria (centro de custo)</label>
                <select
                  className="form-select"
                  value={formData.categoria}
                  onChange={(e) => setFormData({ ...formData, categoria: e.target.value })}
                >
                  <option value="">Sem categoria</option>
                  {categorias.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.nome} ({cat.natureza === 'receita' ? 'receita' : 'despesa'})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Tipo</label>
                  <select
                    className="form-select"
                    value={formData.tipo}
                    onChange={(e) => setFormData({ ...formData, tipo: e.target.value })}
                  >
                    <option value="a_receber">Receber</option>
                    <option value="a_pagar">Pagar</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Valor (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="form-input"
                    required
                    placeholder="0.00"
                    value={formData.valor}
                    onChange={(e) => setFormData({ ...formData, valor: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Data de Vencimento</label>
                <input
                  type="date"
                  className="form-input"
                  required
                  value={formData.vencimento}
                  onChange={(e) => setFormData({ ...formData, vencimento: e.target.value })}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="button" className="btn btn-logout" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Salvando...' : faturaEditando ? 'Salvar Alterações' : 'Salvar Fatura'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  )
}

import { useEffect, useState } from 'react'
import api from '../api/client'
import Layout from '../components/Layout'

export default function Faturas() {
  const [faturas, setFaturas] = useState([])
  const [clientes, setClientes] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [pageError, setPageError] = useState('')
  const [modalError, setModalError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [formData, setFormData] = useState({
    numero: '',
    cliente: '',
    descricao: '',
    tipo: 'a_receber',
    valor: '',
    vencimento: '',
  })

  useEffect(() => {
    fetchFaturas()
    fetchClientes()
  }, [])

  const fetchFaturas = async () => {
    try {
      setLoading(true)
      const res = await api.get('/faturas/')
      setFaturas(res.data.results || res.data)
    } catch (err) {
      console.error(err)
      setPageError('Erro ao carregar faturas.')
    } finally {
      setLoading(false)
    }
  }

  const fetchClientes = async () => {
    try {
      const res = await api.get('/clientes/')
      setClientes(res.data.results || res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setModalError('')
    setSubmitting(true)
    try {
      await api.post('/faturas/', formData)
      setShowModal(false)
      setFormData({ numero: '', cliente: '', descricao: '', tipo: 'a_receber', valor: '', vencimento: '' })
      fetchFaturas()
    } catch (err) {
      console.error(err)
      const data = err.response?.data
      let msg = 'Erro ao criar fatura.'

      if (data) {
        if (typeof data.detail === 'string') msg = data.detail
        else if (typeof data.numero === 'string') msg = `Número: ${data.numero}`
        else if (Array.isArray(data.numero)) msg = `Número: ${data.numero[0]}`
        else if (typeof data.non_field_errors === 'string') msg = data.non_field_errors
        else if (Array.isArray(data.non_field_errors)) msg = data.non_field_errors[0]
      }
      setModalError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const handlePagar = async (id) => {
    setPageError('')
    try {
      await api.post(`/faturas/${id}/pagar/`)
      fetchFaturas()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Não foi possível pagar a fatura.'
      setPageError(msg)
    }
  }

  const handleCancelar = async (id) => {
    if (!window.confirm('Tem certeza que deseja cancelar esta fatura?')) return
    setPageError('')
    try {
      await api.post(`/faturas/${id}/cancelar/`)
      fetchFaturas()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Não foi possível cancelar a fatura.'
      setPageError(msg)
    }
  }

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0)
  }

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Faturas & Contas</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Gestão de contas a pagar e a receber</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setModalError(''); setShowModal(true); }}>
          + Nova Fatura
        </button>
      </div>

      {pageError && <div className="alert-error" style={{ marginBottom: '1rem' }}>{pageError}</div>}

      <div className="card-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>Número</th>
              <th>Cliente / Fornecedor</th>
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
                <td colSpan="8" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Carregando faturas...</td>
              </tr>
            ) : faturas.length === 0 ? (
              <tr>
                <td colSpan="8" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Nenhuma fatura cadastrada.</td>
              </tr>
            ) : (
              faturas.map((f) => (
                <tr key={f.id}>
                  <td style={{ fontWeight: 600 }}>{f.numero}</td>
                  <td>{f.cliente_nome || f.cliente}</td>
                  <td>{f.descricao || '—'}</td>
                  <td>
                    <span style={{ color: f.tipo === 'a_receber' ? 'var(--accent-success)' : 'var(--accent-danger)', fontWeight: 600 }}>
                      {f.tipo === 'a_receber' ? 'A Receber' : 'A Pagar'}
                    </span>
                  </td>
                  <td>{f.vencimento}</td>
                  <td style={{ fontWeight: 700 }}>{formatCurrency(f.valor)}</td>
                  <td>
                    <span className={`badge badge-${f.status}`}>
                      {f.status}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    {f.status !== 'paga' && f.status !== 'cancelada' && (
                      <>
                        <button
                          className="btn btn-success btn-sm"
                          style={{ marginRight: '0.5rem' }}
                          onClick={() => handlePagar(f.id)}
                        >
                          Pagar
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleCancelar(f.id)}
                        >
                          Cancelar
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3 className="modal-title">Nova Fatura</h3>
              <button className="btn-logout" onClick={() => setShowModal(false)}>✕</button>
            </div>

            {modalError && (
              <div className="alert-error" style={{ marginBottom: '1.25rem' }}>
                {modalError}
              </div>
            )}

            <form onSubmit={handleCreate}>
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

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Tipo</label>
                  <select
                    className="form-select"
                    value={formData.tipo}
                    onChange={(e) => setFormData({ ...formData, tipo: e.target.value })}
                  >
                    <option value="a_receber">A Receber</option>
                    <option value="a_pagar">A Pagar</option>
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
                  {submitting ? 'Salvando...' : 'Salvar Fatura'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  )
}
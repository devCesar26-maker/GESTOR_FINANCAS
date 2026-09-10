import { useEffect, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import api from '../api/client'
import Layout from '../components/Layout'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      setLoading(true)
      const res = await api.get('/relatorios/fluxo-caixa/')
      setData(res.data)
    } catch (err) {
      console.error(err)
      setError('Erro ao carregar dados do fluxo de caixa.')
    } finally {
      setLoading(false)
    }
  }

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0)
  }

  // Prepara dados ilustrativos baseados no resumo recebido
  const chartData = data
    ? [
        { name: 'Previsto', A_Receber: Number(data.total_a_receber), A_Pagar: Number(data.total_a_pagar) },
        { name: 'Realizado', Recebido: Number(data.total_recebido), Pago: Number(data.total_pago) },
      ]
    : []

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard Financeiro</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Visão geral do fluxo de caixa e saldos</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={fetchDashboardData}>
          Atualizar
        </button>
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)' }}>Carregando dados...</p>
      ) : error ? (
        <div className="alert-error">{error}</div>
      ) : data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">Total a Receber</div>
              <div className="stat-value positive">{formatCurrency(data.total_a_receber)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total a Pagar</div>
              <div className="stat-value negative">{formatCurrency(data.total_a_pagar)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Recebido</div>
              <div className="stat-value positive">{formatCurrency(data.total_recebido)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Pago</div>
              <div className="stat-value negative">{formatCurrency(data.total_pago)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Saldo Realizado</div>
              <div className={`stat-value ${Number(data.saldo_realizado) >= 0 ? 'positive' : 'negative'}`}>
                {formatCurrency(data.saldo_realizado)}
              </div>
            </div>
          </div>

          <div className="card-table" style={{ padding: '1.5rem', marginTop: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>Comparativo Previsto vs Realizado</h3>
            <div style={{ width: '100%', height: 300 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorReceber" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorPagar" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} />
                  <Area type="monotone" dataKey="A_Receber" stroke="#10b981" fillOpacity={1} fill="url(#colorReceber)" />
                  <Area type="monotone" dataKey="Recebido" stroke="#34d399" fillOpacity={1} fill="url(#colorReceber)" />
                  <Area type="monotone" dataKey="A_Pagar" stroke="#ef4444" fillOpacity={1} fill="url(#colorPagar)" />
                  <Area type="monotone" dataKey="Pago" stroke="#f87171" fillOpacity={1} fill="url(#colorPagar)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      ) : null}
    </Layout>
  )
}
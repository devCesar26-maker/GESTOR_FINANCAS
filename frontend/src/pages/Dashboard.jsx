import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import api from '../api/client'
import Layout from '../components/Layout'

// Ícones SVG inline limpos e modernos
const IconTrendingUp = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
    <polyline points="17 6 23 6 23 12"></polyline>
  </svg>
)

const IconTrendingDown = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 18 13.5 8.5 8.5 13.5 1 6"></polyline>
    <polyline points="17 18 23 18 23 12"></polyline>
  </svg>
)

const IconCheckCircle = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
    <polyline points="22 4 12 14.01 9 11.01"></polyline>
  </svg>
)

const IconCreditCard = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
    <line x1="1" y1="10" x2="23" y2="10"></line>
  </svg>
)

const IconWallet = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4"></path>
    <path d="M4 6v12c0 1.1.9 2 2 2h14v-4"></path>
    <path d="M18 12a2 2 0 0 0-2 2c0 1.1.9 2 2 2h4v-4h-4z"></path>
  </svg>
)

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

  const chartData = data
    ? [
        {
          name: 'Previsto',
          Entradas: Number(data.total_a_receber),
          Saídas: Number(data.total_a_pagar),
        },
        {
          name: 'Realizado',
          Entradas: Number(data.total_recebido),
          Saídas: Number(data.total_pago),
        },
      ]
    : []

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard Financeiro</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            Visão geral em tempo real de caixa e recebimentos
          </p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={fetchDashboardData}>
          Atualizar Dados
        </button>
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)' }}>Carregando dados do dashboard...</p>
      ) : error ? (
        <div className="alert-error">{error}</div>
      ) : data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card stat-card-receber">
              <div className="stat-card-header">
                <span className="stat-label">Total a Receber</span>
                <div className="stat-icon icon-success">
                  <IconTrendingUp />
                </div>
              </div>
              <div className="stat-value positive">{formatCurrency(data.total_a_receber)}</div>
            </div>

            <div className="stat-card stat-card-pagar">
              <div className="stat-card-header">
                <span className="stat-label">Total a Pagar</span>
                <div className="stat-icon icon-danger">
                  <IconTrendingDown />
                </div>
              </div>
              <div className="stat-value negative">{formatCurrency(data.total_a_pagar)}</div>
            </div>

            <div className="stat-card stat-card-recebido">
              <div className="stat-card-header">
                <span className="stat-label">Total Recebido</span>
                <div className="stat-icon icon-success">
                  <IconCheckCircle />
                </div>
              </div>
              <div className="stat-value positive">{formatCurrency(data.total_recebido)}</div>
            </div>

            <div className="stat-card stat-card-pago">
              <div className="stat-card-header">
                <span className="stat-label">Total Pago</span>
                <div className="stat-icon icon-danger">
                  <IconCreditCard />
                </div>
              </div>
              <div className="stat-value negative">{formatCurrency(data.total_pago)}</div>
            </div>

            <div className="stat-card stat-card-saldo">
              <div className="stat-card-header">
                <span className="stat-label">Saldo Realizado</span>
                <div className="stat-icon icon-info">
                  <IconWallet />
                </div>
              </div>
              <div className={`stat-value ${Number(data.saldo_realizado) >= 0 ? 'positive' : 'negative'}`}>
                {formatCurrency(data.saldo_realizado)}
              </div>
            </div>
          </div>

          <div className="card-table chart-card-container">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Comparativo Previsto vs Realizado</h3>
                <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>Análise comparativa de valores previstos e movimentações efetivadas</p>
              </div>
            </div>

            <div style={{ width: '100%', height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.07)" vertical={false} />
                  <XAxis dataKey="name" stroke="#94a3b8" tickLine={false} axisLine={{ stroke: '#334155' }} />
                  <YAxis stroke="#94a3b8" tickLine={false} axisLine={{ stroke: '#334155' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      boxShadow: '0 10px 25px -5px rgba(0,0,0,0.5)',
                      color: '#f8fafc',
                    }}
                  />
                  <Legend wrapperStyle={{ paddingTop: '10px' }} />
                  <Bar dataKey="Entradas" fill="#10b981" radius={[6, 6, 0, 0]} maxBarSize={55} />
                  <Bar dataKey="Saídas" fill="#ef4444" radius={[6, 6, 0, 0]} maxBarSize={55} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      ) : null}
    </Layout>
  )
}
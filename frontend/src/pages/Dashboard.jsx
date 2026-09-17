import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, Cell } from 'recharts'
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

const CORES_CATEGORIAS = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#06b6d4', '#f97316', '#14b8a6', '#ec4899']

const rotuloMoedaCompacta = (val) =>
  new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(val || 0)

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [dre, setDre] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      setLoading(true)
      const [resFluxo, resDre] = await Promise.all([
        api.get('/relatorios/fluxo-caixa/'),
        api.get('/relatorios/dre/'),
      ])
      setData(resFluxo.data)
      setDre(resDre.data)
      setError('')
    } catch (err) {
      console.error(err)
      setError('Erro ao carregar dados do fluxo de caixa.')
    } finally {
      setLoading(false)
    }
  }

  // Exportação: baixa o arquivo autenticado via axios (blob) e dispara o download.
  const exportar = async (rota, formato, nomeArquivo) => {
    try {
      const res = await api.get(rota, { params: { formato }, responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', nomeArquivo)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setError('')
    } catch (err) {
      console.error(err)
      setError(`Falha ao exportar ${nomeArquivo}.`)
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

  // Dados do gráfico por categoria (DRE): receitas e despesas lado a lado.
  const categoriasChart = dre
    ? [
        ...dre.receitas.map((r, i) => ({
          categoria: r.categoria,
          Receitas: Number(r.total),
          Despesas: 0,
          cor: CORES_CATEGORIAS[i % CORES_CATEGORIAS.length],
        })),
        ...dre.despesas.map((d, i) => {
          const existente = dre.receitas.findIndex((r) => r.categoria === d.categoria)
          const cor = existente >= 0 ? CORES_CATEGORIAS[existente % CORES_CATEGORIAS.length] : CORES_CATEGORIAS[i % CORES_CATEGORIAS.length]
          return {
            categoria: d.categoria,
            Receitas: existente >= 0 ? Number(dre.receitas[existente].total) : 0,
            Despesas: Number(d.total),
            cor,
          }
        }),
      ]
    : []

  const exportParams = dre?.periodo?.inicio ? { inicio: dre.periodo.inicio, fim: dre.periodo.fim } : {}

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard Financeiro</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            Visão geral em tempo real de caixa e recebimentos
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-logout btn-sm" onClick={() => exportar('/relatorios/dre/exportar/', 'csv', 'dre.csv')}>
            Exportar CSV
          </button>
          <button className="btn btn-logout btn-sm" onClick={() => exportar('/relatorios/dre/exportar/', 'pdf', 'dre.pdf')}>
            Exportar PDF
          </button>
          <button className="btn btn-primary btn-sm" onClick={fetchDashboardData}>
            Atualizar Dados
          </button>
        </div>
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)' }}>Carregando dados do dashboard...</p>
      ) : error && !data ? (
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
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
                      backgroundColor: '#101d20',
                      borderColor: '#24393e',
                      borderRadius: '2px',
                      border: '1px solid #24393e',
                      color: '#ecf1ef',
                    }}
                  />
                  <Legend wrapperStyle={{ paddingTop: '10px' }} />
                  <Bar dataKey="Entradas" fill="#10b981" radius={[2, 2, 0, 0]} maxBarSize={55} />
                  <Bar dataKey="Saídas" fill="#ef4444" radius={[2, 2, 0, 0]} maxBarSize={55} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ---------------------------------- DRE: por categoria (gráfico) */}
          <div className="card-table chart-card-container">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Receitas e Despesas por Categoria (DRE)</h3>
                <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
                  Centros de custo: agrupamento de faturas pagas por categoria
                </p>
              </div>
            </div>

            {categoriasChart.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Nenhuma fatura paga categorizada no período.
              </p>
            ) : (
              <div style={{ width: '100%', height: 320 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categoriasChart} margin={{ top: 20, right: 30, left: 10, bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.07)" vertical={false} />
                    <XAxis
                      dataKey="categoria"
                      stroke="#94a3b8"
                      tickLine={false}
                      axisLine={{ stroke: '#334155' }}
                      angle={-20}
                      textAnchor="end"
                      interval={0}
                      height={70}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      tickLine={false}
                      axisLine={{ stroke: '#334155' }}
                      tickFormatter={rotuloMoedaCompacta}
                    />
                    <Tooltip
                      formatter={(value) => formatCurrency(value)}
                      contentStyle={{
                        backgroundColor: '#101d20',
                        borderColor: '#24393e',
                        borderRadius: '2px',
                        border: '1px solid #24393e',
                        color: '#ecf1ef',
                      }}
                    />
                    <Legend wrapperStyle={{ paddingTop: '10px' }} />
                    <Bar dataKey="Receitas" radius={[2, 2, 0, 0]} maxBarSize={55}>
                      {categoriasChart.map((entrada, idx) => (
                        <Cell key={`cell-r-${idx}`} fill={entrada.cor} />
                      ))}
                    </Bar>
                    <Bar dataKey="Despesas" radius={[2, 2, 0, 0]} maxBarSize={55}>
                      {categoriasChart.map((entrada, idx) => (
                        <Cell key={`cell-d-${idx}`} fill={entrada.cor} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Resumo textual do DRE */}
            {dre && (
              <div style={{ marginTop: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                <div>
                  <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--accent-success)' }}>Receitas por categoria</h4>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.875rem', lineHeight: 1.9 }}>
                    {dre.receitas.length === 0 && <li style={{ color: 'var(--text-muted)' }}>—</li>}
                    {dre.receitas.map((r) => (
                      <li key={`r-${r.categoria}`}>
                        {r.categoria}: <strong style={{ color: 'var(--accent-success)' }}>{formatCurrency(r.total)}</strong>
                      </li>
                    ))}
                    <li style={{ borderTop: '1px solid var(--border-color, #24393e)', marginTop: '0.35rem', paddingTop: '0.35rem' }}>
                      <strong>Total: {formatCurrency(dre.total_receitas)}</strong>
                    </li>
                  </ul>
                </div>
                <div>
                  <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--accent-danger)' }}>Despesas por categoria</h4>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.875rem', lineHeight: 1.9 }}>
                    {dre.despesas.length === 0 && <li style={{ color: 'var(--text-muted)' }}>—</li>}
                    {dre.despesas.map((d) => (
                      <li key={`d-${d.categoria}`}>
                        {d.categoria}: <strong style={{ color: 'var(--accent-danger)' }}>{formatCurrency(d.total)}</strong>
                      </li>
                    ))}
                    <li style={{ borderTop: '1px solid var(--border-color, #24393e)', marginTop: '0.35rem', paddingTop: '0.35rem' }}>
                      <strong>Total: {formatCurrency(dre.total_despesas)}</strong>
                    </li>
                  </ul>
                </div>
                <div>
                  <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Resultado do período</h4>
                  <p style={{ fontSize: '1.4rem', fontWeight: 700, margin: 0, color: Number(dre.resultado) >= 0 ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                    {formatCurrency(dre.resultado)}
                  </p>
                </div>
              </div>
            )}
          </div>
        </>
      ) : null}
    </Layout>
  )
}

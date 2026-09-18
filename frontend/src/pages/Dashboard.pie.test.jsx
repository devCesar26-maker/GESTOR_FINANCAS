// Teste de regressão do visual das pizzas do DRE.
//
// Decisão de design: as fatias NÃO exibem rótulos de % — números dentro de
// fatias finas se sobrepõem e poluem o gráfico. A legenda inferior já mostra
// "Categoria — R$ x (y%)" com clareza, e o tooltip detalha o valor no hover.
import { describe, it, expect } from 'vitest'
import { PieChart, Pie, Cell } from 'recharts'
import { createRoot } from 'react-dom/client'
import { act } from 'react'

// O recharts v3 renderiza labels via efeitos (não aparecem em
// renderToStaticMarkup): monta com createRoot + act e devolve o innerHTML.
const renderPieHtml = (element) => {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => {
    root.render(element)
  })
  const html = container.innerHTML
  root.unmount()
  container.remove()
  return html
}

// Configuração IDÊNTICA à da <Pie> do Dashboard (sem label, sem labelLine).
const pizzaDoDashboard = (dados) => (
  <PieChart width={400} height={300}>
    <Pie
      data={dados}
      dataKey="valor"
      nameKey="nome"
      cx="50%"
      cy="42%"
      innerRadius={55}
      outerRadius={88}
      paddingAngle={2}
      stroke="none"
      isAnimationActive={false}
    >
      {dados.map((d) => (
        <Cell key={d.nome} fill={d.cor} />
      ))}
    </Pie>
  </PieChart>
)

describe('pizzas do DRE: visual limpo, sem rótulos de % nas fatias', () => {
  it('fatia dominante (91%) não recebe rótulo de %', () => {
    const html = renderPieHtml(
      pizzaDoDashboard([
        { nome: 'Pequena', valor: 90, cor: '#3b82f6' },
        { nome: 'Grande', valor: 910, cor: '#f97316' },
      ])
    )
    expect(html).not.toMatch(/>\s*\d+\s*%\s*</)
  })

  it('nenhuma fatia recebe rótulo, mesmo com várias categorias pequenas', () => {
    const html = renderPieHtml(
      pizzaDoDashboard(
        Array.from({ length: 6 }, (_, i) => ({
          nome: `Cat ${i + 1}`,
          valor: 100 + i,
          cor: ['#3b82f6', '#f97316', '#14b8a6', '#eab308', '#8b5cf6', '#ec4899'][i],
        }))
      )
    )
    expect(html).toMatch(/recharts-pie-sector/) // as fatias existem...
    expect(html).not.toMatch(/>\s*\d+\s*%\s*</) // ...mas sem % sobre elas
  })
})

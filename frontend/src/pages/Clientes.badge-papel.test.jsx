// Teste de componente do BadgePapel (página Clientes).
//
// "Ambos" é um caso real de negócio: uma entidade pode ser cliente E
// fornecedor do mesmo gestor. O badge correspondente é neutro (cinza),
// com os dois pontos de cor (verde = cliente, laranja = fornecedor) e
// rótulo explícito "Cliente/Fornecedor" — enquanto os papéis exclusivos
// mantêm os badges verde/laranja que já existiam.
import { describe, it, expect } from 'vitest'
import { createRoot } from 'react-dom/client'
import { act } from 'react'

// Necessário para usar `act` fora do react-dom/test-utils (React 19 + jsdom);
// sem isso o Vitest só imprime o aviso "not configured to support act(...)".
globalThis.IS_REACT_ACT_ENVIRONMENT = true

import { BadgePapel } from './Clientes'

// React 19 renderiza de forma assíncrona: monta com createRoot + act e
// aguarda o innerHTML refletir a árvore renderizada.
async function renderHtml(element) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  await act(async () => {
    root.render(element)
  })
  const html = container.innerHTML
  root.unmount()
  container.remove()
  return html
}

describe('BadgePapel na listagem de clientes', () => {
  it('papel "ambos" renderiza badge neutro com os dois pontos e rótulo Cliente/Fornecedor', async () => {
    const html = await renderHtml(<BadgePapel papel="ambos" />)

    expect(html).toContain('badge-ambos')
    expect(html).toContain('papel-dot-verde')
    expect(html).toContain('papel-dot-laranja')
    expect(html).toContain('Cliente/Fornecedor')
  })

  it('papel "cliente" mantém o badge verde com rótulo legível', async () => {
    const html = await renderHtml(<BadgePapel papel="cliente" />)

    expect(html).toContain('badge-paga')
    expect(html).not.toContain('badge-pendente')
    expect(html).toContain('Cliente')
  })

  it('papel "fornecedor" mantém o badge laranja com rótulo legível', async () => {
    const html = await renderHtml(<BadgePapel papel="fornecedor" />)

    expect(html).toContain('badge-pendente')
    expect(html).not.toContain('badge-paga')
    expect(html).toContain('Fornecedor')
  })
})

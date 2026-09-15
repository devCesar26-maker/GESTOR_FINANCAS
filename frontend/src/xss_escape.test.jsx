import React from 'react'
import ReactDOM from 'react-dom/client'
import { describe, expect, it, vi } from 'vitest'

// React escapa por padrão todo texto renderizado com {dato}: um payload
// XSS guardado na API (ver test_seguridad.py no backend) aparece como
// texto, nunca como script. Este teste comprova esse comportamento — a
// auditoria confirmou que o projeto não usa dangerouslySetInnerHTML.
//
// Nota: React 19 renderiza de forma assíncrona, por isso esperamos a
// primeira renderização com vi.waitFor antes de verificar o HTML.
describe('escape XSS por padrão do React', () => {
  it('um nome com <script> se renderiza como texto, não como script', async () => {
    const payload = '<script>alert(1)</script>'
    const container = document.createElement('div')
    ReactDOM.createRoot(container).render(<div>{payload}</div>)

    await vi.waitFor(() => {
      expect(container.innerHTML).toContain('&lt;script&gt;')
    })
    expect(container.innerHTML).not.toContain('<script>alert(1)</script>')
  })
})
import { useEffect } from 'react'

/**
 * Modal de confirmação customizado (substitui window.confirm nativo).
 *
 * Props:
 * - titulo: string exibida no cabeçalho do modal
 * - mensagem: texto explicativo da ação
 * - textoConfirmar: rótulo do botão de confirmação (default "Confirmar")
 * - textoCancelar: rótulo do botão de cancelar (default "Voltar")
 * - textoProcessando: rótulo exibido durante o processamento (default "Processando...")
 * - variante: classe do botão de confirmação (default "btn-danger";
 *   use "btn-primary" para ações não destrutivas, ex.: logout)
 * - aoConfirmar: callback executado ao confirmar
 * - aoCancelar: callback executado ao cancelar/fechar
 * - processando: desabilita os botões enquanto a ação roda (evita duplo clique)
 */
export default function ConfirmDialog({
  titulo,
  mensagem,
  textoConfirmar = 'Confirmar',
  textoCancelar = 'Voltar',
  textoProcessando = 'Processando...',
  variante = 'btn-danger',
  aoConfirmar,
  aoCancelar,
  processando = false,
}) {
  // Esc fecha o modal e trava o scroll do body enquanto aberto.
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') aoCancelar()
    }
    document.addEventListener('keydown', onKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
    }
  }, [aoCancelar])

  return (
    <div
      className="modal-overlay"
      onClick={aoCancelar}
      role="dialog"
      aria-modal="true"
      aria-label={titulo}
    >
      <div className="modal-card" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">{titulo}</h3>
          <button className="btn-logout" onClick={aoCancelar} aria-label="Fechar">✕</button>
        </div>

        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
          {mensagem}
        </p>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button className="btn btn-logout" onClick={aoCancelar} disabled={processando}>
            {textoCancelar}
          </button>
          <button
            className={`btn ${variante}`}
            onClick={aoConfirmar}
            disabled={processando}
            autoFocus
          >
            {processando ? textoProcessando : textoConfirmar}
          </button>
        </div>
      </div>
    </div>
  )
}

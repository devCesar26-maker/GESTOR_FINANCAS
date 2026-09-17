import { describe, expect, it } from 'vitest'

import {
  limparTelefone,
  montarLinkCobranca,
  montarLinkWhatsApp,
  temTelefoneValido,
} from './whatsapp'

describe('limparTelefone', () => {
  it('remove símbolos e adiciona DDI 55 em celular de 11 dígitos', () => {
    expect(limparTelefone('(11) 98765-4321')).toBe('5511987654321')
    expect(limparTelefone('11 98765 4321')).toBe('5511987654321')
    expect(limparTelefone('+55 11 98765-4321')).toBe('5511987654321')
  })

  it('adiciona DDI 55 em fixo de 10 dígitos', () => {
    expect(limparTelefone('(11) 3456-7890')).toBe('551134567890')
    expect(limparTelefone('1134567890')).toBe('551134567890')
  })

  it('mantém números que já possuem DDI 55 (12 ou 13 dígitos)', () => {
    expect(limparTelefone('551134567890')).toBe('551134567890')
    expect(limparTelefone('5511987654321')).toBe('5511987654321')
  })

  it('retorna null para vazio, e-mail ou números inválidos', () => {
    expect(limparTelefone('')).toBeNull()
    expect(limparTelefone(null)).toBeNull()
    expect(limparTelefone('contato@empresa.com')).toBeNull()
    expect(limparTelefone('123')).toBeNull()
    expect(limparTelefone('119876543211234567')).toBeNull()
  })
})

describe('temTelefoneValido', () => {
  it('true apenas quando existe telefone utilizável', () => {
    expect(temTelefoneValido('(11) 98765-4321')).toBe(true)
    expect(temTelefoneValido('contato@empresa.com')).toBe(false)
    expect(temTelefoneValido('')).toBe(false)
  })
})

describe('montarLinkWhatsApp', () => {
  it('gera wa.me com número limpo e mensagem codificada', () => {
    const link = montarLinkWhatsApp('Maria Silva', '(11) 98765-4321')
    expect(link).toBe(
      'https://wa.me/5511987654321?text=' +
        encodeURIComponent('Olá Maria Silva, tudo bem? Entro em contato referente à sua conta no FinFlow.'),
    )
    expect(link).toMatch(/^https:\/\/wa\.me\/5511987654321\?text=/)
  })

  it('codifica acentos, espaços e vírgulas da mensagem', () => {
    const link = montarLinkWhatsApp('João', '11987654321')
    const texto = decodeURIComponent(link.split('text=')[1])
    expect(texto).toBe(
      'Olá João, tudo bem? Entro em contato referente à sua conta no FinFlow.',
    )
  })

  it('retorna null quando não há telefone válido', () => {
    expect(montarLinkWhatsApp('Sem Fone', 'contato@x.com')).toBeNull()
    expect(montarLinkWhatsApp('Sem Fone', '')).toBeNull()
  })
})

describe('montarLinkCobranca (faturas)', () => {
  const fatura = {
    cliente_nome: 'Maria Silva',
    cliente_telefone: '(11) 98765-4321',
    numero: 'FAT-2026-0042',
    valor: '1500.00',
    vencimento: '2026-09-30',
  }

  it('gera wa.me do cliente com numero, valor e vencimento na mensagem', () => {
    const link = montarLinkCobranca(fatura)
    expect(link).toMatch(/^https:\/\/wa\.me\/5511987654321\?text=/)
    const texto = decodeURIComponent(link.split('text=')[1])
    expect(texto).toBe(
      'Olá Maria Silva, lembramos que a fatura FAT-2026-0042 no valor de R$ 1.500,00 vence em 30/09/2026.',
    )
  })

  it('retorna null sem telefone válido do cliente', () => {
    expect(montarLinkCobranca({ ...fatura, cliente_telefone: '' })).toBeNull()
    expect(montarLinkCobranca(null)).toBeNull()
  })
})

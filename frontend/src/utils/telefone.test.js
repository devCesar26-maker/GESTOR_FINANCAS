import { describe, expect, it } from 'vitest'

import { mascararTelefone } from './telefone'

describe('mascararTelefone', () => {
  it('formata celular de 11 dígitos', () => {
    expect(mascararTelefone('11987654321')).toBe('(11) 98765-4321')
  })

  it('formata fixo de 10 dígitos', () => {
    expect(mascararTelefone('1134567890')).toBe('(11) 3456-7890')
  })

  it('formata progressivamente enquanto digita', () => {
    expect(mascararTelefone('1')).toBe('(1')
    expect(mascararTelefone('11')).toBe('(11')
    expect(mascararTelefone('119')).toBe('(11) 9')
    expect(mascararTelefone('1198765')).toBe('(11) 9876-5')
  })

  it('ignora símbolos já mascarados e limita a 11 dígitos', () => {
    expect(mascararTelefone('(11) 98765-4321')).toBe('(11) 98765-4321')
    expect(mascararTelefone('11987654321123456789')).toBe('(11) 98765-4321')
  })

  it('retorna string vazia para entrada vazia/nula', () => {
    expect(mascararTelefone('')).toBe('')
    expect(mascararTelefone(null)).toBe('')
    expect(mascararTelefone('abc')).toBe('')
  })
})

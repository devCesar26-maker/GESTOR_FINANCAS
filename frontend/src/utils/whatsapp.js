/**
 * Utilitário de WhatsApp para contato com clientes.
 *
 * Regras (números brasileiros):
 * - Remove TUDO que não é dígito (espaços, parênteses, hífens, "+", etc.).
 * - 10 dígitos  (DDD + fixo, ex.: 1134567890)  -> prefixa DDI 55.
 * - 11 dígitos  (DDD + celular, ex.: 11987654321) -> prefixa DDI 55.
 * - 12/13 dígitos começando com 55 (já têm DDI) -> mantém como está.
 * - Qualquer outro caso (vazio, e-mail, número curto, DDI estranho) -> inválido.
 */

const TAMANHO_FIXO_UF = 10 // DDD + telefone fixo
const TAMANHO_CEL_UF = 11 // DDD + celular com "9"
const TAMANHO_COM_DDI = [12, 13] // 55 + 10 OU 55 + 11

/**
 * Limpa e normaliza o telefone para o padrão do wa.me (só dígitos, com DDI).
 * @param {string|null} valor Telefone como digitado no cadastro.
 * @returns {string|null} Número normalizado (ex.: "5511987654321") ou null.
 */
export function limparTelefone(valor) {
  if (!valor || typeof valor !== 'string') return null

  const digitos = valor.replace(/\D/g, '')
  if (!digitos) return null // e-mail ou campo sem nenhum número

  if (digitos.length === TAMANHO_FIXO_UF || digitos.length === TAMANHO_CEL_UF) {
    return `55${digitos}` // número nacional sem DDI: adiciona o 55
  }

  if (
    TAMANHO_COM_DDI.includes(digitos.length) &&
    digitos.startsWith('55')
  ) {
    return digitos // já tem DDI do Brasil
  }

  return null // comprimento inválido (ex.: ramal, 0800, número estrangeiro)
}

/**
 * Indica se o cliente tem telefone utilizável para WhatsApp.
 */
export function temTelefoneValido(valor) {
  return limparTelefone(valor) !== null
}

/**
 * Monta a URL https://wa.me/{numero}?text={mensagem} ou null sem telefone.
 * A mensagem é codificada com encodeURIComponent (acentos, espaços, vírgulas).
 */
export function montarLinkWhatsApp(nome, telefone) {
  const numero = limparTelefone(telefone)
  if (!numero) return null

  const mensagem = `Olá ${String(nome || '').trim()}, tudo bem? Entro em contato referente à sua conta no FinFlow.`
  return `https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`
}

/**
 * Monta o link de COBRANÇA de uma fatura pendente ("A Receber"):
 * wa.me/{telefone_do_cliente}?text="Olá {nome}, lembramos que a fatura
 * {numero} no valor de R$ {valor} vence em {data}."
 *
 * @param {object} fatura { cliente_nome, cliente_telefone, numero, valor, vencimento }
 * @returns {string|null} URL ou null se o cliente não tiver telefone válido.
 */
export function montarLinkCobranca(fatura) {
  if (!fatura) return null

  const numero = limparTelefone(fatura.cliente_telefone)
  if (!numero) return null

  const [ano, mes, dia] = String(fatura.vencimento || '').split('-')
  const dataFormatada = ano && mes && dia ? `${dia}/${mes}/${ano}` : String(fatura.vencimento || '')

  const valorFormatado = new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 2,
  }).format(Number(fatura.valor || 0))

  const mensagem = `Olá ${String(fatura.cliente_nome || '').trim()}, lembramos que a fatura ${fatura.numero} no valor de R$ ${valorFormatado} vence em ${dataFormatada}.`
  return `https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`
}

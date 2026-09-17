/**
 * Máscara de telefone brasileiro para inputs: formata enquanto o usuário digita.
 *
 * "(11987654321" -> "(11) 98765-4321" (celular, 11 dígitos)
 * "(1134567890"  -> "(11) 3456-7890"  (fixo, 10 dígitos)
 * Aceita colar valores com símbolos; limita a 11 dígitos.
 */
export function mascararTelefone(valor) {
  const digitos = String(valor || '')
    .replace(/\D/g, '')
    .slice(0, 11)

  if (digitos.length === 0) return ''

  const ddd = digitos.slice(0, 2)
  const resto = digitos.slice(2)

  if (digitos.length <= 2) return `(${ddd}`

  if (digitos.length <= 10) {
    const parte1 = resto.slice(0, 4)
    const parte2 = resto.slice(4)
    return parte2 ? `(${ddd}) ${parte1}-${parte2}` : `(${ddd}) ${parte1}`
  }

  // 11 dígitos: celular com "9"
  return `(${ddd}) ${resto.slice(0, 5)}-${resto.slice(5)}`
}

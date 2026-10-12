import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleOAuthProvider, useGoogleOAuth } from '@react-oauth/google'
import { loginComGoogle } from '../api/client'
import { useAuth } from '../auth/AuthContext'

// Botão "Entrar com Google" (Google Identity Services via @react-oauth/google).
//
// Fluxo: o Google entrega o id_token (JWT assinado pelo Google, com e-mail
// JÁ verificado) e o backend o troca pelos JWTs nativos do FinFlow — access
// em memória + refresh no cookie httpOnly, exatamente como o login por
// senha. Em caso de sucesso o usuário vai direto para o Dashboard.
//
// O componente PRECISA estar dentro de <GoogleOAuthProvider clientId=...>
// (montado em main.jsx). Sem VITE_GOOGLE_CLIENT_ID no build, o provider não
// é montado e o botão não deve ser renderizado.
//
// Por que renderizamos manualmente (window.google.accounts.id) em vez de
// usar <GoogleLogin> da lib: o componente da lib chama
// google.accounts.id.initialize() a cada mount/update (e de novo quando a
// prop width muda) — origem do warning "initialize() is called multiple
// times". Aqui initialize() roda UMA VEZ por carregamento de página
// (guarda inicializadoRef) e renderButton() a cada mount do botão.
export default function BotaoGoogle({ texto = 'Entrar com Google' }) {
  return (
    <GoogleOAuthProvider clientId={import.meta.env?.VITE_GOOGLE_CLIENT_ID}>
      <BotaoGoogleInterno texto={texto} />
    </GoogleOAuthProvider>
  )
}

function BotaoGoogleInterno({ texto }) {
  const navigate = useNavigate()
  const { login: loginComAccess } = useAuth()
  const { clientId, scriptLoadedSuccessfully } = useGoogleOAuth()
  const containerRef = useRef(null)
  const inicializadoRef = useRef(false)
  const [larguraBotao, setLarguraBotao] = useState(null)

  // Callbacks em refs: o callback registrado no initialize() é fixo, mas
  // as funções de navegação/erro acessam sempre a versão mais recente.
  const callbackRef = useRef(null)
  callbackRef.current = async (credentialResponse) => {
    if (!credentialResponse?.credential) {
      console.error('Resposta do Google sem credential.')
      alert('Não foi possível entrar com o Google. Tente novamente.')
      return
    }
    try {
      const { access } = await loginComGoogle(credentialResponse.credential)
      loginComAccess(access)
      navigate('/')
    } catch (err) {
      console.error(err)
      alert(
        err.response?.data?.detail ??
          'Não foi possível entrar com o Google. Tente novamente.',
      )
    }
  }

  // initialize() UMA VEZ por carregamento de página (guarda contra dupla
  // execução — Resolve o warning "initialize() is called multiple times").
  useEffect(() => {
    if (!scriptLoadedSuccessfully || !clientId || inicializadoRef.current) return
    window.google?.accounts?.id?.initialize({
      client_id: clientId,
      callback: (credentialResponse) => callbackRef.current(credentialResponse),
      auto_select: false,
      ux_mode: 'popup',
    })
    inicializadoRef.current = true
  }, [scriptLoadedSuccessfully, clientId])

  // Width NUMÉRICO em px: a API do GSI não aceita "100%" (warning
  // "Provided button width is invalid: 100%"). Medimos a largura real do
  // container com ResizeObserver e seguimos os limites do GSI
  // (200–400 px); fallback 368 px se ResizeObserver indisponível.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return undefined
    if (typeof ResizeObserver === 'undefined') {
      setLarguraBotao(368)
      return undefined
    }
    const observer = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0]?.contentRect?.width ?? 0)
      if (w >= 200) setLarguraBotao(Math.min(w, 400))
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // renderButton() a cada mount, com largura já definida (evita passar
  // width=null no primeiro render).
  useEffect(() => {
    if (!scriptLoadedSuccessfully || !clientId || !larguraBotao) return
    window.google?.accounts?.id?.renderButton(containerRef.current, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      shape: 'rectangular',
      text: texto.includes('Cadastrar') ? 'signup_with' : 'signin_with',
      width: larguraBotao,
      locale: 'pt_BR',
      logo_alignment: 'left',
    })
    // O GSI renderButton substitui o conteúdo do container a cada chamada:
    // sem cleanup para desmonte simples (o efeito roda de novo ao mudar
    // largura/texto, redesenhando o botão).
  }, [scriptLoadedSuccessfully, clientId, larguraBotao, texto])

  if (!clientId) return null

  return (
    <div
      ref={containerRef}
      className="google-btn-container"
      style={{ width: '100%', display: 'flex', justifyContent: 'center', margin: '0.5rem 0' }}
    />
  )
}

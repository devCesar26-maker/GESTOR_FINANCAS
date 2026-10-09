import { useNavigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { loginComGoogle } from '../api/client'

// Botão "Entrar com Google" (Google Identity Services via @react-oauth/google).
//
// Fluxo: o Google entrega o id_token (JWT assinado pelo Google, com e-mail
// JÁ verificado) e o backend o troca pelos JWTs nativos do FinFlow — access
// em memória + refresh no cookie httpOnly, exatamente como o login por
// senha. Em caso de sucesso o usuário vai direto para o Dashboard.
//
// É preciso envolver a aplicação em <GoogleOAuthProvider clientId=...>
// (ver main.jsx). Sem VITE_GOOGLE_CLIENT_ID no build, o provider não é
// montado e o botão não deve ser renderizado.
export default function BotaoGoogle({ texto = 'Entrar com Google' }) {
  const navigate = useNavigate()

  const clientId = import.meta.env?.VITE_GOOGLE_CLIENT_ID
  if (!clientId) return null

  return (
    <div className="google-btn-container" style={{ width: '100%', display: 'flex', justifyContent: 'center', margin: '0.5rem 0' }}>
      <GoogleLogin
        clientId={clientId}
        buttonText={texto}
        text={texto.includes('Cadastrar') ? 'signup_with' : 'signin_with'}
        theme="outline"
        size="large"
        shape="rectangular"
        width="100%"
        locale="pt_BR"
        // Popup (default): o id_token chega direto no callback, sem redirect.
        onSuccess={async (credentialResponse) => {
          try {
            await loginComGoogle(credentialResponse.credential)
            navigate('/')
          } catch (err) {
            console.error(err)
            alert(
              err.response?.data?.detail ??
                'Não foi possível entrar com o Google. Tente novamente.',
            )
          }
        }}
        onError={() => {
          console.error('Falha no login com Google')
          alert('Não foi possível entrar com o Google. Tente novamente.')
        }}
        // select_account: permite trocar de conta Google no popup.
        context="signin"
        ux_mode="popup"
        auto_select={false}
        useOneTap={false}
      />
    </div>
  )
}

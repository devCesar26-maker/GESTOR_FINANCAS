import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import App from './App'
import './styles.css'

// Client ID do Google OAuth (Google Cloud Console → Credenciais). É variável
// de BUILD do Vite (embutida no bundle); o MESMO valor deve estar no backend
// (GOOGLE_CLIENT_ID) — o id_token é validado com audience = este client id.
// Sem a variável, o provider não é montado e o botão Google não aparece.
const googleClientId = import.meta.env?.VITE_GOOGLE_CLIENT_ID

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {googleClientId ? (
      <GoogleOAuthProvider clientId={googleClientId}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </GoogleOAuthProvider>
    ) : (
      // Sem GOOGLE configurado (dev sem credenciais): app funciona
      // normalmente, apenas sem o botão "Entrar com Google".
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )}
  </React.StrictMode>,
)
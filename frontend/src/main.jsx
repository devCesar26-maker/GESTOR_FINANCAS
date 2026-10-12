import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth/AuthContext'
import './styles.css'

// Client ID do Google OAuth (Google Cloud Console → Credenciais). É variável
// de BUILD do Vite (embutida no bundle); o MESMO valor deve estar no backend
// (GOOGLE_CLIENT_ID) — o id_token é validado com audience = este client id.
// Sem a variável, o provider não é montado e o botão Google não aparece.
const googleClientId = import.meta.env?.VITE_GOOGLE_CLIENT_ID

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* Sem GOOGLE configurado (dev sem credenciais): app funciona
        normalmente, apenas sem o botão "Entrar com Google" (
        BotaoGoogle.jsx lê o clientId do GoogleOAuthContext e retorna null). */}
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
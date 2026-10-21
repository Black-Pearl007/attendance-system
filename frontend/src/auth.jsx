import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, tokenStore } from './api'

const AuthCtx = createContext(null)
export const useAuth = () => useContext(AuthCtx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const onLogout = () => setUser(null)
    window.addEventListener('auth:logout', onLogout)
    if (!tokenStore.get()) { setReady(true) } else {
      api.get('/auth/me').then(setUser).catch(() => tokenStore.clear()).finally(() => setReady(true))
    }
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password })
    tokenStore.set(res.access_token)
    setUser(res.user)
  }
  const logout = () => { tokenStore.clear(); setUser(null) }

  return <AuthCtx.Provider value={{ user, ready, login, logout }}>{children}</AuthCtx.Provider>
}

export function RequireAuth({ children }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <div className="center-screen">Loading…</div>
  if (!user) return <Navigate to="/login" state={{ from: loc }} replace />
  return children
}

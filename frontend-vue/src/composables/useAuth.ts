import { ref } from 'vue'

const SESSION_KEY = 'agent-session'
const authed = ref(sessionStorage.getItem(SESSION_KEY) === 'admin')

export function isAuthenticated() {
  return sessionStorage.getItem(SESSION_KEY) === 'admin'
}

export function useAuth() {
  function login(username: string, password: string) {
    const ok = username.trim() === 'admin' && password === 'admin'
    if (ok) {
      sessionStorage.setItem(SESSION_KEY, 'admin')
      authed.value = true
    }
    return ok
  }

  function logout() {
    sessionStorage.removeItem(SESSION_KEY)
    authed.value = false
  }

  return { authed, login, logout }
}

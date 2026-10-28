import { defineStore } from 'pinia'
import http from '../api/http'

export const useAuth = defineStore('auth', {
  state: () => ({ token: localStorage.getItem('token'), user: null }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    can: (s) => (code) => !!s.user?.permissions?.includes(code),
  },
  actions: {
    async login(email, password) {
      const body = new URLSearchParams({ username: email, password })
      const { data } = await http.post('/auth/login', body)
      if (data.mfa_required) return { mfaRequired: true, mfaToken: data.mfa_token }
      await this.finishLogin(data.access_token)
      return { mfaRequired: false }
    },
    async loginWithCode(mfaToken, code) {
      const { data } = await http.post('/auth/login/2fa', { mfa_token: mfaToken, code })
      await this.finishLogin(data.access_token)
    },
    async finishLogin(accessToken) {
      this.token = accessToken
      localStorage.setItem('token', accessToken)
      await this.fetchMe()
    },
    async register(payload) {
      await http.post('/auth/register', payload)
    },
    async fetchMe() {
      const { data } = await http.get('/auth/me')
      this.user = data
    },
    async logout() {
      try {
        await http.post('/auth/logout')
      } catch {
        /* ignore, we clear local state anyway */
      }
      this.token = null
      this.user = null
      localStorage.removeItem('token')
    },
  },
})
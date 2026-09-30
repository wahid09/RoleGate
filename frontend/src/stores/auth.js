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
      this.token = data.access_token
      localStorage.setItem('token', this.token)
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
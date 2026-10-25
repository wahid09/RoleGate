import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'
import AdminLayout from '../layouts/AdminLayout.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import ForgotPassword from '../views/ForgotPassword.vue'
import ResetPassword from '../views/ResetPassword.vue'
import VerifyEmail from '../views/VerifyEmail.vue'
import Dashboard from '../views/Dashboard.vue'
import Users from '../views/Users.vue'
import Roles from '../views/Roles.vue'
import Permissions from '../views/Permissions.vue'
import AuditLog from '../views/AuditLog.vue'
import Profile from '../views/Profile.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { guest: true } },
    { path: '/register', component: Register, meta: { guest: true } },
    { path: '/forgot-password', component: ForgotPassword, meta: { guest: true } },
    { path: '/reset-password', component: ResetPassword, meta: { guest: true } },
    { path: '/verify-email', component: VerifyEmail },
    {
      path: '/',
      component: AdminLayout,
      meta: { auth: true },
      children: [
        { path: '', component: Dashboard, meta: { permission: 'dashboard:view' } },
        { path: 'profile', component: Profile },

        // Dev Console
        { path: 'dev', redirect: '/dev/users' },
        { path: 'dev/users', component: Users, meta: { permission: 'users:read' } },
        { path: 'dev/roles', component: Roles, meta: { permission: 'roles:read' } },
        { path: 'dev/permissions', component: Permissions, meta: { permission: 'permissions:read' } },
        { path: 'dev/audit', component: AuditLog, meta: { permission: 'audit:read' } },

        // old URLs
        { path: 'users', redirect: '/dev/users' },
        { path: 'roles', redirect: '/dev/roles' },
        { path: 'audit', redirect: '/dev/audit' },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()

  if (to.matched.some((r) => r.meta.auth) && !auth.isLoggedIn) return '/login'
  if (to.meta.guest && auth.isLoggedIn) return '/'

  if (auth.isLoggedIn && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return '/login'
    }
  }

  const need = to.meta.permission
  if (need && !auth.can(need)) return '/profile'
})

export default router
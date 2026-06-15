import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/pages/Login.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/components/Layout.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', name: 'Dashboard', component: () => import('@/pages/Dashboard.vue') },
        { path: 'accounts', name: 'Accounts', component: () => import('@/pages/Accounts.vue') },
        { path: 'transactions', name: 'Transactions', component: () => import('@/pages/Transactions.vue') },
        { path: 'alerts', name: 'Alerts', component: () => import('@/pages/Alerts.vue') },
        { path: 'analytics', name: 'Analytics', component: () => import('@/pages/Analytics.vue') },
        { path: 'budgets', name: 'Budgets', component: () => import('@/pages/Budgets.vue') },
        { path: 'ai-monitor', name: 'AIMonitor', component: () => import('@/pages/AIMonitor.vue'), meta: { roles: ['admin'] } },
        { path: 'users', name: 'Users', component: () => import('@/pages/Users.vue'), meta: { roles: ['admin'] } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return '/login'
  }
  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role)) {
    return '/dashboard'
  }
})

export default router

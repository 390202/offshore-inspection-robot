import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('../views/Login.vue') },
    { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
    { path: '/alarm', component: () => import('../views/Alarm.vue') },
    { path: '/device', component: () => import('../views/Device.vue') },
    { path: '/track', component: () => import('../views/Track.vue') },
    { path: '/task', component: () => import('../views/Task.vue') },
    { path: '/logs', component: () => import('../views/SystemLogs.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
  ],
  scrollBehavior: () => ({ top: 0 })
})
router.beforeEach(to => to.path !== '/' && !localStorage.getItem('token') ? '/' : true)
export default router

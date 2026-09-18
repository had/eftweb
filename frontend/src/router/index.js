import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import FamilyListView from '@/views/FamilyListView.vue'
import FamilyLandingView from '@/views/FamilyLandingView.vue'
import StocksView from '@/views/StocksView.vue'
import TaxReturnsView from '@/views/TaxReturnsView.vue'
import TaxReturnDetailView from '@/views/TaxReturnDetailView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/families',
      name: 'families',
      component: FamilyListView,
    },
    {
      path: '/family',
      name: 'family',
      component: FamilyLandingView,
    },
    {
      path: '/stocks',
      name: 'stocks',
      component: StocksView,
    },
    {
      path: '/tax-returns',
      name: 'tax-returns',
      component: TaxReturnsView,
    },
    {
      path: '/tax-returns/:taxReturnId',
      name: 'tax-return',
      component: TaxReturnDetailView,
    },
  ],
})

export default router

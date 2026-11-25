import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import FamilyListView from '@/views/FamilyListView.vue'
import FamilyLandingView from '@/views/FamilyLandingView.vue'
import StocksView from '@/views/StocksView.vue'
import RealEstateView from '@/views/RealEstateView.vue'
import StockDetailView from '@/views/StockDetailView.vue'
import TaxReturnsView from '@/views/TaxReturnsView.vue'
import TaxReturnDetailView from '@/views/TaxReturnDetailView.vue'
import SettingsView from '@/views/SettingsView.vue'

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
      path: '/real-estate',
      name: 'real-estate',
      component: RealEstateView,
    },
    {
      path: '/stocks/:stockId',
      name: 'stock',
      component: StockDetailView,
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
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView,
    },
  ],
})

export default router

import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import ProjectListView from '@/views/ProjectListView.vue'
import StocksView from '@/views/StocksView.vue'
import TaxesView from '@/views/TaxesView.vue'
import TaxView from '@/views/TaxView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/projects',
      name: 'projects',
      component: ProjectListView,
    },
    {
      path: '/stocks',
      name: 'stocks',
      component: StocksView,
    },
    {
      path: '/taxes',
      name: 'taxes',
      component: TaxesView,
    },
    {
      path: '/taxes/:taxId',
      name: 'tax',
      component: TaxView,
    },
  ],
})

export default router

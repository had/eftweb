<script setup>
import { RouterLink, useRoute } from 'vue-router'
import { useTemplateRef } from 'vue'
import ProjectPicker from './ProjectPicker.vue'
import { useProjectStore } from '@/stores/project'

const projectPicker = useTemplateRef('project-picker')
const projectStore = useProjectStore()

const isCurrentPath = (viewPath) => {
  const route = useRoute()
  return route.path === viewPath
}

const toggle = (event) => {
  if (projectPicker.value?.projectMenu) {
    projectPicker.value.projectMenu.toggle(event)
  }
}

const isProjectSelected = () => {
  return !!projectStore.projectId
}
</script>

<template>
  <nav class="navbar">
    <div class="navsection">
      <RouterLink to="/" class="logo py-4 self-center">Easy French Tax</RouterLink>
      <RouterLink
        to="/stocks"
        :class="[
          'item',
          isCurrentPath('/stocks') ? 'background-color:#000 border-l-2 border-l-gray-500' : '',
        ]"
        >Stocks</RouterLink
      >
      <RouterLink
        to="/taxes"
        :class="[
          'item',
          isCurrentPath('/taxes') ? 'background-color:#000 border-l-2 border-l-gray-500' : '',
        ]"
        >Taxes</RouterLink
      >
    </div>
    <div class="navsection">
      <Button
        type="button"
        :severity="isProjectSelected() ? 'secondary' : 'contrast'"
        :label="isProjectSelected() ? projectStore.projectName : 'Select Project'"
        icon="pi pi-book"
        @click="toggle"
        class="m-3"
      />
      <ProjectPicker ref="project-picker" />
    </div>
  </nav>
</template>

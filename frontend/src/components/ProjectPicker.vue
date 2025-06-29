<script setup>
import { ref, onMounted, useTemplateRef } from 'vue'
import axios from 'axios'
import { useProjectStore } from '@/stores/project'

const projectStore = useProjectStore()

const projectMenu = useTemplateRef('project-picker-menu')
defineExpose({
  projectMenu,
})

const projectItems = ref([
  {
    label: 'Projects',
    items: [],
  },
])

const projects = ref([])

onMounted(async () => {
  try {
    const response = await axios.get('http://localhost:5001/api/projects')
    projects.value = response.data
    const projectLabels = response.data.map((p) => ({
      label: p.name,
      command: () => {
        projectStore.setCurrentProject(p)
      },
    }))
    projectItems.value[0].items = projectLabels
  } catch (error) {
    console.error('Error fetching projects:', error)
  }
})
</script>

<template>
  <Menu ref="project-picker-menu" :popup="true" :model="projectItems" />
</template>

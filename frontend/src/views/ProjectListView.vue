<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useProjectStore } from '@/stores/project'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const router = useRouter()
const projectStore = useProjectStore()
const projects = ref([])
const loading = ref(true)
const error = ref(null)

onMounted(async () => {
  try {
    const response = await axios.get('/api/projects')
    projects.value = response.data
    console.log(`Result of querying /api/projects: ${projects.value}`)
  } catch (err) {
    console.error('Failed to fetch projects:', err)
    error.value = 'Failed to load projects. Please try again.'
  } finally {
    loading.value = false
  }
})

const selectProject = (project) => {
  projectStore.setCurrentProject(project)
  router.push('/taxes')
}
</script>

<template>
  <div class="p-8">
    <div class="mb-8">
      <h1 class="text-3xl font-bold mb-2">Select a Project</h1>
      <p class="text-muted-foreground">
        Choose a project to view its tax statements and stock portfolio
      </p>
    </div>

    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <Card v-for="i in 3" :key="i" class="animate-pulse">
        <CardHeader>
          <div class="h-6 bg-muted rounded w-3/4"></div>
        </CardHeader>
        <CardContent>
          <div class="h-4 bg-muted rounded w-1/2"></div>
        </CardContent>
      </Card>
    </div>

    <div v-else-if="error" class="text-center py-12">
      <p class="text-destructive text-lg">{{ error }}</p>
      <Button class="mt-4" @click="() => window.location.reload()">Retry</Button>
    </div>

    <div
      v-else-if="projects.length === 0"
      class="text-center py-12 text-muted-foreground"
    >
      <p class="text-lg">No projects found</p>
    </div>

    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
    >
      <Card
        v-for="project in projects"
        :key="project.id"
        class="cursor-pointer hover:shadow-lg transition-shadow"
        @click="selectProject(project)"
      >
        <CardHeader>
          <CardTitle>{{ project.name }}</CardTitle>
          <CardDescription v-if="project.description">
            {{ project.description }}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div class="flex justify-between items-center text-sm text-muted-foreground">
            <span v-if="project.taxstatements">
              {{ project.taxstatements.length }} tax statement{{
                project.taxstatements.length !== 1 ? 's' : ''
              }}
            </span>
            <Button variant="ghost" size="sm">Select →</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

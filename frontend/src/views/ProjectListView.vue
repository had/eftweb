<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useProjectStore } from '@/stores/project'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import ProjectFormModal from '@/components/ProjectFormModal.vue'
import { Pencil, Plus } from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()
const projects = ref([])
const loading = ref(true)
const error = ref(null)
const showModal = ref(false)
const editingProject = ref(null)

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

const openCreateModal = () => {
  editingProject.value = null
  showModal.value = true
}

const openEditModal = (project) => {
  editingProject.value = project
  showModal.value = true
}

const handleProjectSaved = async () => {
  const response = await axios.get('/api/projects')
  projects.value = response.data
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

    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <Card class="cursor-pointer hover:shadow-lg transition-shadow border-2 border-dashed p-6" @click="openCreateModal">
        <div class="flex flex-col items-center justify-center gap-3 h-48">
          <Plus class="h-8 w-8 text-muted-foreground" />
          <div class="text-lg font-semibold">Create New Project</div>
          <div class="text-sm text-muted-foreground text-center">Add a new tax project</div>
        </div>
      </Card>
      <Card v-for="i in 2" :key="i" class="animate-pulse p-6">
        <div class="flex flex-col gap-4 h-48">
          <div class="h-6 bg-muted rounded w-3/4"></div>
          <div class="h-4 bg-muted rounded w-1/2"></div>
          <div class="h-4 bg-muted rounded w-1/2"></div>
          <div class="flex-1"></div>
          <div class="h-9 bg-muted rounded w-full"></div>
        </div>
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

    <div v-else>
      <TooltipProvider>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <!-- Create New Project Card -->
          <Card
            class="cursor-pointer hover:shadow-lg transition-shadow border-2 border-dashed p-6"
            @click="openCreateModal"
          >
            <div class="flex flex-col items-center justify-center gap-3 h-48">
              <Plus class="h-8 w-8 text-muted-foreground" />
              <div class="text-lg font-semibold">Create New Project</div>
              <div class="text-sm text-muted-foreground text-center">Add a new tax project</div>
            </div>
          </Card>

          <!-- Existing Projects -->
          <Card
            v-for="project in projects"
            :key="project.id"
            class="cursor-pointer hover:shadow-lg transition-shadow relative group p-6"
            @click="selectProject(project)"
          >
            <Button
              variant="ghost"
              size="icon"
              class="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity"
              @click.stop="openEditModal(project)"
            >
              <Pencil class="h-4 w-4" />
            </Button>

            <div class="flex flex-col gap-4 h-48">
              <!-- Title with tooltip -->
              <Tooltip>
                <TooltipTrigger as-child>
                  <div class="text-xl font-bold truncate pr-8">
                    {{ project.name }}
                  </div>
                </TooltipTrigger>
                <TooltipContent v-if="project.name && project.name.length > 20">
                  {{ project.name }}
                </TooltipContent>
              </Tooltip>

              <!-- Marital Status -->
              <div class="text-sm text-muted-foreground">
                {{ project.married ? 'Married' : 'Single' }}
              </div>

              <!-- Number of Children -->
              <div class="text-sm text-muted-foreground">
                {{ project.nb_children }} {{ project.nb_children === 1 ? 'child' : 'children' }}
              </div>

              <!-- Spacer -->
              <div class="flex-1"></div>

              <!-- Select Button -->
              <Button variant="outline" class="w-full" @click.stop="selectProject(project)">
                Select →
              </Button>
            </div>
          </Card>
        </div>
      </TooltipProvider>
    </div>

    <!-- Project Form Modal -->
    <ProjectFormModal
      v-model:open="showModal"
      :project="editingProject"
      @saved="handleProjectSaved"
    />
  </div>
</template>

import { ref } from 'vue'
import { defineStore } from 'pinia'

const projectLocalStorageKey = 'current_project'

export const useProjectStore = defineStore('project', () => {
  const projectName = ref('')
  const projectId = ref(0)
  const taxStatementsVersion = ref(0)

  const locProjectJSON = localStorage.getItem(projectLocalStorageKey)
  if (locProjectJSON) {
    const locProject = JSON.parse(locProjectJSON)
    projectName.value = locProject.name
    projectId.value = locProject.id
  }

  function setCurrentProject(project) {
    projectName.value = project.name
    projectId.value = project.id
    localStorage.setItem(
      projectLocalStorageKey,
      JSON.stringify({
        name: projectName.value,
        id: projectId.value,
      }),
    )
  }

  function clearCurrentProject() {
    projectName.value = ''
    projectId.value = 0
    localStorage.removeItem(projectLocalStorageKey)
  }

  function refreshTaxStatements() {
    taxStatementsVersion.value += 1
  }

  return {
    projectName,
    projectId,
    taxStatementsVersion,
    setCurrentProject,
    clearCurrentProject,
    refreshTaxStatements,
  }
})

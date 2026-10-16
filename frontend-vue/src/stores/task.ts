import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TaskStatus, TaskStatusResponse } from '@/types'

export const useTaskStore = defineStore('task', () => {
  const taskId = ref<string | null>(null)
  const taskStatus = ref<TaskStatus | null>(null)
  const statusData = ref<TaskStatusResponse | null>(null)

  function setTaskId(id: string) {
    taskId.value = id
  }

  function setTaskStatus(status: TaskStatus) {
    taskStatus.value = status
  }

  function setStatusData(data: TaskStatusResponse) {
    statusData.value = data
    taskStatus.value = data.status
  }

  return { taskId, taskStatus, statusData, setTaskId, setTaskStatus, setStatusData }
})

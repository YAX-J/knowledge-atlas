import { nextTick, onScopeDispose, ref, type Ref } from 'vue'
import { listRepositorySnapshots, listSnapshotFiles, importSnapshotCommit } from '../api/knowledgeAtlas'
import type { ApiProject, RepositorySnapshotList, RepositorySnapshotFileList, RepositorySnapshotFile, SourceRepository } from '../api/knowledgeAtlas'
import type { IngestionErrors, IngestionLoading, WorkspaceNav } from '../types'

interface Options {
  project: Ref<ApiProject | null>; activeNav: Ref<WorkspaceNav>
  loading: IngestionLoading; errors: IngestionErrors; notice: Ref<string>
  selectedSourceId: Ref<string>; selectedTaskId: Ref<string | null>
  clearSourceSelection: () => void
  selectSource: (id: string, taskId: string | null) => Promise<void>
  loadSources: (page?: number) => Promise<void>; refreshSource: (page?: number) => Promise<void>
  errorMessage: (error: unknown) => string
}

export function useRepositorySnapshots(options: Options) {
  const { project, activeNav, loading, errors, notice, selectedSourceId, selectedTaskId,
    clearSourceSelection, selectSource, loadSources, refreshSource, errorMessage } = options
  const snapshotRepository = ref<SourceRepository | null>(null)
  const snapshots = ref<RepositorySnapshotList | null>(null)
  const snapshotsLoading = ref(false)
  const snapshotsError = ref('')
  const snapshotsPage = ref(1)
  const importingSnapshotId = ref('')
  let snapshotsRequest = 0
  const filesSnapshotId = ref('')
  const snapshotFiles = ref<RepositorySnapshotFileList | null>(null)
  const snapshotFilesLoading = ref(false)
  const snapshotFilesError = ref('')
  const snapshotFilesPage = ref(1)
  let snapshotFilesRequest = 0

  function clearSnapshotFiles() {
    snapshotFilesRequest++
    filesSnapshotId.value = ''
    snapshotFiles.value = null
    snapshotFilesLoading.value = false
    snapshotFilesError.value = ''
    snapshotFilesPage.value = 1
  }

  async function closeSnapshotFiles() {
    const snapshotId = filesSnapshotId.value
    clearSnapshotFiles()
    await nextTick()
    document.querySelector<HTMLButtonElement>(`[data-snapshot-files="${snapshotId}"]`)?.focus()
  }

  async function loadSnapshotFilePage(snapshotId: string, page = 1) {
    const projectId = project.value?.id
    const repositoryId = snapshotRepository.value?.id
    if (!projectId || !repositoryId) return
    const request = ++snapshotFilesRequest
    filesSnapshotId.value = snapshotId
    snapshotFilesPage.value = page
    snapshotFiles.value = null
    snapshotFilesLoading.value = true
    snapshotFilesError.value = ''
    await nextTick()
    if (request === snapshotFilesRequest) {
      const panel = document.getElementById('snapshot-files-panel')
      panel?.focus({ preventScroll: true })
      panel?.scrollIntoView({ block: 'start', behavior: 'instant' })
    }
    try {
      const result = await listSnapshotFiles(projectId, repositoryId, snapshotId, page)
      if (request === snapshotFilesRequest && project.value?.id === projectId) snapshotFiles.value = result
    } catch (error) {
      if (request === snapshotFilesRequest) snapshotFilesError.value = errorMessage(error)
    } finally {
      if (request === snapshotFilesRequest) snapshotFilesLoading.value = false
    }
  }

  async function openSnapshotFile(file: RepositorySnapshotFile) {
    if (!file.source_id || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit) return
    const projectId = project.value?.id
    await selectSource(file.source_id, file.task_id)
    await nextTick()
    if (project.value?.id !== projectId || selectedSourceId.value !== file.source_id || (activeNav.value !== 'sources' && activeNav.value !== 'projects')) return
    const reader = document.getElementById('source-reader')
    reader?.focus({ preventScroll: true })
    reader?.scrollIntoView({ block: 'start', behavior: 'instant' })
  }

  function clearSnapshots() {
    clearSnapshotFiles()
    snapshotsRequest++
    snapshotRepository.value = null
    snapshots.value = null
    snapshotsError.value = ''
    snapshotsLoading.value = false
    snapshotsPage.value = 1
  }

  async function loadSnapshots(repository: SourceRepository, page = 1) {
    const projectId = project.value?.id
    if (!projectId) return
    const request = ++snapshotsRequest
    clearSnapshotFiles()
    snapshotsPage.value = page
    snapshotRepository.value = repository
    snapshots.value = null
    snapshotsLoading.value = true
    snapshotsError.value = ''
    try {
      const result = await listRepositorySnapshots(projectId, repository.id, page, 10)
      if (request === snapshotsRequest && project.value?.id === projectId) snapshots.value = result
    } catch (error) {
      if (request === snapshotsRequest && project.value?.id === projectId) snapshotsError.value = errorMessage(error)
    } finally {
      if (request === snapshotsRequest) snapshotsLoading.value = false
    }
  }

  async function saveSnapshotCommit(snapshotId: string) {
    const projectId = project.value?.id
    const repository = snapshotRepository.value
    if (!projectId || !repository || loading.commit || loading.upload || loading.task || loading.sync || loading.activity || loading.remote) return
    loading.commit = true
    errors.commit = ''
    importingSnapshotId.value = snapshotId
    const page = snapshots.value?.page ?? 1
    try {
      const result = await importSnapshotCommit(projectId, repository.id, snapshotId)
      if (project.value?.id !== projectId) return
      notice.value = result.reused ? '已复用提交资料与解析任务，请核对当前状态。' : '提交说明已加入资料。解析后可显式抽取并审核知识。'
      clearSourceSelection()
      selectedSourceId.value = result.source_id
      selectedTaskId.value = result.task_id
      await Promise.all([loadSources(1), refreshSource(), loadSnapshots(repository, page)])
      await nextTick()
      if (project.value?.id === projectId && (activeNav.value === 'sources' || activeNav.value === 'projects')) {
        const reader = document.getElementById('source-reader')
        reader?.focus({ preventScroll: true })
        reader?.scrollIntoView({ block: 'start', behavior: 'instant' })
      }
    } catch (error) {
      if (project.value?.id === projectId) errors.commit = errorMessage(error)
    } finally {
      loading.commit = false
      importingSnapshotId.value = ''
    }
  }

  onScopeDispose(clearSnapshots)
  return { snapshotRepository, snapshots, snapshotsLoading, snapshotsError, snapshotsPage, importingSnapshotId, filesSnapshotId, snapshotFiles, snapshotFilesLoading, snapshotFilesError, snapshotFilesPage, clearSnapshotFiles, closeSnapshotFiles, loadSnapshotFilePage, openSnapshotFile, clearSnapshots, loadSnapshots, saveSnapshotCommit }
}

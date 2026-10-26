import { onScopeDispose, watch, type Ref } from 'vue'
import { importGithubWorkItems, resolveGithubRepository, resolveLocalRepository, syncGithubRepository, uploadSource, runTask } from '../api/knowledgeAtlas'
import type { ApiProject, ProcessingTask, SourceList, SourceRepositoryList, SourceUploadResult } from '../api/knowledgeAtlas'
import type { IngestionErrors, IngestionLoading } from '../types'

interface Dependencies {
  project: Ref<ApiProject | null>; repositories: Ref<SourceRepositoryList | null>; sources: Ref<SourceList | null>
  selectedSourceId: Ref<string>; selectedTaskId: Ref<string | null>; task: Ref<ProcessingTask | null>; notice: Ref<string>
  loading: IngestionLoading; errors: IngestionErrors; locked: () => boolean
  prepareSource: () => void; loadSources: (page?: number) => Promise<void>
  loadRepositories: (page?: number) => Promise<void>; refreshSource: () => Promise<void>
  errorMessage: (error: unknown) => string
}

export function useSourceImport(dependencies: Dependencies) {
  const { project, repositories, sources, selectedSourceId, selectedTaskId, task, notice, loading, errors,
    prepareSource, loadSources, loadRepositories, refreshSource, errorMessage, locked } = dependencies
  let generation = 0, disposed = false
  const current = (projectId: string, captured: number) => !disposed && captured === generation && project.value?.id === projectId
  async function registerGithubRepository(input: {
    remoteUrl: string
    localRepositoryId?: string
  }) {
    const projectId = project.value?.id
    const captured = generation
    if (disposed || locked() || !projectId || loading.remote || loading.sync || loading.activity || loading.upload || loading.task || loading.commit) return
    loading.remote = true
    errors.remote = ''
    notice.value = ''
    try {
      const repository = await resolveGithubRepository(
        projectId, input.remoteUrl, input.localRepositoryId,
      )
      if (!current(projectId, captured)) return
      notice.value = repository.kind === 'local_folder'
        ? `已把本地仓库“${repository.name}”关联到 ${repository.remote_url}。`
        : `已登记 GitHub 仓库“${repository.name}”，尚未导入远程文件。`
      await loadRepositories(1)
    } catch (error) {
      if (current(projectId, captured)) errors.remote = errorMessage(error)
    } finally {
      loading.remote = false
    }
  }

  async function syncRegisteredGithubRepository(input: {
    repositoryId: string
    ref?: string
    rescan?: boolean
  }) {
    const projectId = project.value?.id
    const captured = generation
    if (disposed || locked() || !projectId || loading.sync || loading.activity || loading.remote || loading.upload || loading.task || loading.commit) return
    loading.sync = true
    errors.sync = errors.activity = ''
    notice.value = '正在从 GitHub 读取仓库快照…'
    try {
      const result = await syncGithubRepository(projectId, input.repositoryId, input.ref, input.rescan)
      if (!current(projectId, captured)) return
      const selected = [...result.items].reverse().find(
        item => item.status !== 'deleted' && item.source_id && item.task_id,
      )
      if (selected?.source_id && selected.task_id) {
        prepareSource()
        selectedSourceId.value = selected.source_id
        selectedTaskId.value = selected.task_id
      }
      notice.value = `GitHub ${result.ref}@${result.commit_sha.slice(0, 7)} 同步完成：新增 ${result.imported_count}、复用 ${result.reused_count}、未变 ${result.unchanged_count}、重命名 ${result.renamed_count}、删除 ${result.deleted_count}、跳过 ${result.skipped_count}${result.truncated ? '；结果达到导入上限' : ''}${result.deletion_detection_complete ? '' : '；本次无法完整判断删除'}。`
      await Promise.all([loadSources(1), loadRepositories(repositories.value?.page ?? 1)])
      if (current(projectId, captured) && selectedSourceId.value) await refreshSource()
    } catch (error) {
      if (current(projectId, captured)) {
        notice.value = ''
        errors.sync = errorMessage(error)
      }
    } finally {
      loading.sync = false
    }
  }

  async function importRegisteredGithubActivity(repositoryId: string) {
    const projectId = project.value?.id
    const captured = generation
    if (disposed || locked() || !projectId || loading.activity || loading.sync || loading.remote || loading.upload || loading.task || loading.commit) return
    loading.activity = true
    errors.activity = errors.sync = ''
    notice.value = '正在从 GitHub 读取最近更新的 Issue、Pull Request、Review 与 thread 状态…'
    try {
      const result = await importGithubWorkItems(projectId, repositoryId)
      if (!current(projectId, captured)) return
      const selected = [...result.items].reverse().find(
        item => item.status !== 'skipped' && item.source_id && item.task_id,
      )
      if (selected?.source_id && selected.task_id) {
        prepareSource()
        selectedSourceId.value = selected.source_id
        selectedTaskId.value = selected.task_id
      }
      const truncatedComments = result.items.filter(item => item.comments_truncated).length
      const truncatedReviews = result.items.filter(
        item => item.reviews_truncated || item.review_comments_truncated,
      ).length
      const truncatedThreads = result.items.filter(item => item.review_threads_truncated).length
      const tokenRequiredThreads = result.items.filter(
        item => item.review_threads_status === 'token_required',
      ).length
      const reviewThreadCount = result.items.reduce(
        (total, item) => total + item.review_threads_count,
        0,
      )
      const resolvedReviewThreadCount = result.items.reduce(
        (total, item) => total + item.resolved_review_threads_count,
        0,
      )
      notice.value = `GitHub Issue/PR 导入完成：工作项新增 ${result.imported_count}、复用 ${result.reused_count}、跳过 ${result.skipped_count}；Review 快照新增 ${result.review_imported_count}、复用 ${result.review_reused_count}、跳过 ${result.review_skipped_count}；Review thread ${reviewThreadCount} 个（已解决 ${resolvedReviewThreadCount}）${result.truncated ? '；结果达到 20 项上限' : ''}${truncatedComments ? `；${truncatedComments} 项普通评论达到导入上限` : ''}${truncatedReviews ? `；${truncatedReviews} 项 Review 活动达到导入上限` : ''}${truncatedThreads ? `；${truncatedThreads} 项 thread 状态达到导入上限` : ''}${tokenRequiredThreads ? `；${tokenRequiredThreads} 项 thread 状态需要后端 GITHUB_TOKEN` : ''}。`
      await Promise.all([loadSources(1), loadRepositories(repositories.value?.page ?? 1)])
      if (current(projectId, captured) && selectedSourceId.value) await refreshSource()
    } catch (error) {
      if (current(projectId, captured)) {
        notice.value = ''
        errors.activity = errorMessage(error)
      }
    } finally {
      loading.activity = false
    }
  }

  async function uploadFiles(files: File[]) {
    const projectId = project.value?.id
    const captured = generation
    if (disposed || locked() || !projectId || !files.length || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit) return
    loading.upload = true
    try {
      errors.upload = ''
      notice.value = ''
      // Prevent an older automatic selection from replacing the upload result.
      prepareSource()
      const failures: string[] = []
      let lastResult: SourceUploadResult | null = null
      const folderPath = files[0]?.webkitRelativePath ?? ''
      const folderRoot = folderPath.split('/').filter(Boolean)[0] ?? ''
      let repositoryId: string | undefined
      let repositoryName = ''
      if (folderRoot) {
        try {
          const repository = await resolveLocalRepository(projectId, folderRoot)
          if (!current(projectId, captured)) return
          repositoryId = repository.id
          repositoryName = repository.name
          notice.value = `已识别本地仓库“${repository.name}”，正在接收资料。`
        } catch (error) {
          if (current(projectId, captured)) errors.upload = errorMessage(error)
          loading.upload = false
          return
        }
      }
      for (const [index, file] of files.entries()) {
        if (!current(projectId, captured)) return
        const fileLabel = file.webkitRelativePath || file.name
        notice.value = `正在接收第 ${index + 1} / ${files.length} 份资料：${fileLabel}`
        try {
          const pathParts = file.webkitRelativePath.split('/').filter(Boolean)
          const repositoryPath = repositoryId
            ? pathParts.slice(1).join('/') || file.name
            : undefined
          lastResult = await uploadSource(
            projectId, file, repositoryPath, repositoryId,
          )
        } catch (error) {
          failures.push(`${fileLabel}：${errorMessage(error)}`)
        }
      }
      if (!current(projectId, captured)) return
      const succeeded = files.length - failures.length
      if (repositoryId) await loadRepositories(1)
      if (!current(projectId, captured)) return
      if (lastResult) {
        selectedSourceId.value = lastResult.source_id
        selectedTaskId.value = lastResult.task_id
        notice.value = `${repositoryId ? `本地仓库“${repositoryName}”` : '单文件'}已接收 ${succeeded} / ${files.length} 份资料。相同仓库中的相同内容会复用已有资料，请查看当前解析状态。`
        await Promise.all([loadSources(1), refreshSource()])
      } else {
        notice.value = ''
      }
      if (failures.length) {
        if (!current(projectId, captured)) return
        const visibleFailures = failures.slice(0, 3).join('；')
        errors.upload = `有 ${failures.length} 份资料上传失败：${visibleFailures}${failures.length > 3 ? `；另有 ${failures.length - 3} 份未列出` : ''}`
      }
    } catch (error) {
      if (current(projectId, captured)) errors.upload = errorMessage(error)
    } finally { loading.upload = false; loading.sources = false }
  }


  async function parseSource() {
    const taskId = selectedTaskId.value
    const projectId = project.value?.id, captured = generation
    if (disposed || locked() || !projectId || !taskId || loading.create || loading.task || loading.upload || loading.sync || loading.activity || loading.commit) return
    loading.task = true
    errors.task = ''
    try {
      const result = await runTask(taskId)
      if (!current(projectId, captured) || selectedTaskId.value !== taskId) return
      task.value = result
      if (task.value.status === 'failed') {
        const message = task.value.error?.message
        errors.task = typeof message === 'string' ? message : '解析失败，请重试。'
      }
      await Promise.all([refreshSource(), loadSources(sources.value?.page ?? 1)])
      if (current(projectId, captured) && task.value?.status === 'failed') errors.task = '解析失败，请重试解析。'
    } catch (error) {
      if (current(projectId, captured)) errors.task = errorMessage(error)
    } finally {
      loading.task = false
    }
  }


  watch(() => project.value?.id, () => { generation++ }, { flush:'sync' })
  onScopeDispose(() => { disposed = true; generation++ })
  return { registerGithubRepository, syncRegisteredGithubRepository, importRegisteredGithubActivity, uploadFiles, parseSource }
}

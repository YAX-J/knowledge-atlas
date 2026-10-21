<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppHeader from './components/AppHeader.vue'
import SideRail from './components/SideRail.vue'
import KnowledgeGraph from './components/KnowledgeGraph.vue'
import InsightPanel from './components/InsightPanel.vue'
import TimelineBar from './components/TimelineBar.vue'
import SourceWorkspace from './components/SourceWorkspace.vue'
import CandidateReview from './components/CandidateReview.vue'
import ProjectGraph from './components/ProjectGraph.vue'
import QuestionWorkspace from './components/QuestionWorkspace.vue'
import { ApiError } from './api/client'
import {
  createProject, getSource, getTask, listProjects, listSourceChunks, listSources,
  runTask, uploadSource, extractKnowledge, getExtraction, listCandidates, resolveCandidate,
  getProjectGraph, getEntityDetail, getRelationshipDetail, searchKnowledge, rebuildProjectEmbeddings, askQuestion,
  getJavaCodeStructure,
  importGithubWorkItems, listRepositories, resolveGithubRepository, resolveLocalRepository, syncGithubRepository,
} from './api/knowledgeAtlas'
import type {
  ApiProject, ApiProjectList, ApiSource, ProcessingTask, SourceChunkList, SourceList,
  CandidateList, ExtractionResult, JavaCodeStructure, SourceRepositoryList, SourceUploadResult,
} from './api/knowledgeAtlas'
import { edges, evidences, nodes, nodeTypeLabels, timelinePoints } from './mock/data'
import type { IngestionErrors, IngestionLoading, NodeType, WorkspaceNav, ReviewDecision, ProjectGraphData, EntityDetail, RelationshipDetail, KnowledgeSearchMode, KnowledgeSearchResult, QuestionAnswer } from './types'

const selectedId = ref('event-driven')
const activeNav = ref<WorkspaceNav>(import.meta.env.VITE_DATA_SOURCE === 'api' ? 'sources' : 'graph')
const timelineIndex = ref(timelinePoints.length - 1)
const panelOpen = ref(true)
const filterOpen = ref(false)
const allTypes = Object.keys(nodeTypeLabels) as NodeType[]
const visibleTypes = ref<NodeType[]>([...allTypes])
const projects = ref<ApiProjectList | null>(null)
const project = ref<ApiProject | null>(null)
const repositories = ref<SourceRepositoryList | null>(null)
const sources = ref<SourceList | null>(null)
const selectedSourceId = ref('')
const selectedTaskId = ref<string | null>(null)
const source = ref<ApiSource | null>(null)
const task = ref<ProcessingTask | null>(null)
const chunks = ref<SourceChunkList | null>(null)
const codeStructure = ref<JavaCodeStructure | null>(null)
const notice = ref('')
const loading = reactive<IngestionLoading>({ projects: false, create: false, repositories: false, remote: false, sync: false, activity: false, sources: false, upload: false, detail: false, task: false, chunks: false, structure: false })
const errors = reactive<IngestionErrors>({ projects: '', create: '', repositories: '', remote: '', sync: '', activity: '', sources: '', upload: '', detail: '', task: '', chunks: '', structure: '' })
let projectsRequest = 0
let repositoriesRequest = 0
let sourcesRequest = 0
let detailRequest = 0
let chunksRequest = 0
let structureRequest = 0
let reviewsRequest = 0
let reviewAction = 0
const candidates = ref<CandidateList | null>(null)
const extraction = ref<ExtractionResult | null>(null)
const reviewsLoading = ref(false)
const extracting = ref(false)
const resolving = ref('')
const reviewsError = ref('')
const reviewsNotice = ref('')
const realGraph = ref<ProjectGraphData | null>(null)
const realEntityDetail = ref<EntityDetail | null>(null)
const realRelationshipDetail = ref<RelationshipDetail | null>(null)
const graphLoading = ref(false)
const graphDetailLoading = ref(false)
const graphError = ref('')
const graphDetailError = ref('')
const graphSelectedId = ref('')
const graphSelectionKind = ref<'entity' | 'relationship'>('entity')
const graphCenter = ref('')
const graphType = ref('')
const graphDepth = ref(1)
let graphRequest = 0
let graphDetailRequest = 0
const searchResult = ref<KnowledgeSearchResult | null>(null)
const searchLoading = ref(false)
const searchRebuilding = ref(false)
const searchError = ref('')
const searchErrorAction = ref<'search' | 'rebuild'>('search')
const searchNotice = ref('')
let searchRequest = 0
let embeddingRebuildRequest = 0
let searchQuery = ''
let searchTypes = ''
let searchMode: KnowledgeSearchMode = 'keyword'
const questionResult = ref<QuestionAnswer | null>(null)
const questionLoading = ref(false)
const questionError = ref('')
let questionText = ''
let questionRequest = 0

function clearQuestion() {
  questionRequest++
  questionResult.value = null
  questionError.value = ''
  questionLoading.value = false
  questionText = ''
}

async function runQuestion(question: string) {
  const projectId = project.value?.id
  if (!projectId || questionLoading.value) return
  const request = ++questionRequest
  questionText = question
  questionLoading.value = true
  questionError.value = ''
  questionResult.value = null
  try {
    const result = await askQuestion(projectId, question)
    if (request === questionRequest && project.value?.id === projectId) questionResult.value = result
  } catch (error) {
    if (request === questionRequest && project.value?.id === projectId) questionError.value = errorMessage(error)
  } finally {
    if (request === questionRequest) questionLoading.value = false
  }
}

function retryQuestion() {
  if (questionText) void runQuestion(questionText)
}

function clearSearch() {
  searchRequest++
  embeddingRebuildRequest++
  searchResult.value = null
  searchError.value = ''
  searchErrorAction.value = 'search'
  searchNotice.value = ''
  searchLoading.value = false
  searchRebuilding.value = false
  searchQuery = searchTypes = ''
  searchMode = 'keyword'
}

async function runSearch(query: string, types: string, mode: KnowledgeSearchMode) {
  const projectId = project.value?.id
  if (!projectId) return
  const request = ++searchRequest
  searchQuery = query
  searchTypes = types
  searchMode = mode
  searchLoading.value = true
  searchErrorAction.value = 'search'
  searchError.value = ''
  searchResult.value = null
  try {
    const result = await searchKnowledge(projectId, query, types, mode)
    if (request === searchRequest && project.value?.id === projectId) searchResult.value = result
  } catch (error) {
    if (request === searchRequest) searchError.value = errorMessage(error)
  } finally {
    if (request === searchRequest) searchLoading.value = false
  }
}

async function rebuildSemanticIndex() {
  const projectId = project.value?.id
  if (!projectId || searchRebuilding.value) return
  const request = ++embeddingRebuildRequest
  searchRebuilding.value = true
  searchErrorAction.value = 'rebuild'
  searchError.value = searchNotice.value = ''
  try {
    const result = await rebuildProjectEmbeddings(projectId)
    if (request !== embeddingRebuildRequest || project.value?.id !== projectId) return
    searchNotice.value = `语义索引已更新：新增或刷新 ${result.updated_count} 条，复用 ${result.reused_count} 条。`
    if (searchQuery && searchMode !== 'keyword') await runSearch(searchQuery, searchTypes, searchMode)
  } catch (error) {
    if (request === embeddingRebuildRequest && project.value?.id === projectId) searchError.value = errorMessage(error)
  } finally {
    if (request === embeddingRebuildRequest) searchRebuilding.value = false
  }
}

async function openSearchEntity(id: string) {
  const projectId = project.value?.id
  await selectGraphEntity(id)
  await nextTick()
  if (project.value?.id === projectId && graphSelectedId.value === id) document.getElementById('formal-knowledge-detail')?.focus()
}

async function openQuestionEntity(id: string) {
  if (!project.value) return
  activeNav.value = 'projectGraph'
  clearSearch()
  graphType.value = ''
  graphSelectedId.value = id
  await loadRealGraph(id)
  await nextTick()
  if (graphSelectedId.value === id) document.getElementById('formal-knowledge-detail')?.focus()
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return '无法确认请求结果。请检查后端服务和网络连接，刷新后重试。'
}

function clearSourceSelection() {
  reviewsRequest++
  reviewAction++
  candidates.value = null
  extraction.value = null
  reviewsLoading.value = extracting.value = false
  resolving.value = reviewsError.value = reviewsNotice.value = ''
  detailRequest++
  chunksRequest++
  structureRequest++
  selectedSourceId.value = ''
  selectedTaskId.value = null
  source.value = null
  task.value = null
  chunks.value = null
  codeStructure.value = null
  errors.detail = errors.task = errors.chunks = errors.structure = ''
  loading.detail = loading.chunks = loading.structure = false
}

async function loadProjects(page = 1) {
  const request = ++projectsRequest
  loading.projects = true
  errors.projects = ''
  try {
    const result = await listProjects(page)
    if (request !== projectsRequest) return
    projects.value = result
    if (!project.value && result.items[0]) selectProject(result.items[0])
  } catch (error) {
    if (request === projectsRequest) errors.projects = errorMessage(error)
  } finally {
    if (request === projectsRequest) loading.projects = false
  }
}

function selectProject(value: ApiProject) {
  if (loading.upload || loading.task || loading.remote || loading.sync || loading.activity) return
  clearQuestion()
  project.value = value
  clearSearch()
  graphRequest++
  graphDetailRequest++
  realGraph.value = null
  realEntityDetail.value = realRelationshipDetail.value = null
  graphSelectedId.value = graphCenter.value = graphType.value = ''
  graphLoading.value = graphDetailLoading.value = false
  repositories.value = null
  repositoriesRequest++
  sources.value = null
  sourcesRequest++
  clearSourceSelection()
  errors.repositories = errors.remote = errors.sync = errors.activity = errors.sources = errors.upload = ''
  notice.value = ''
  void Promise.all([loadRepositories(1), loadSources(1)])
}

async function addProject(input: { name: string; description: string }) {
  if (loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity) return
  loading.create = true
  errors.create = ''
  try {
    const result = await createProject(input)
    // Invalidate any older list response before selecting the new project.
    projectsRequest++
    selectProject(result)
    notice.value = `项目“${result.name}”已创建。可以上传第一篇笔记了。`
    await loadProjects(1)
  } catch (error) {
    errors.create = errorMessage(error)
  } finally {
    loading.create = false
  }
}

async function loadSources(page = 1) {
  const projectId = project.value?.id
  if (!projectId) return
  const request = ++sourcesRequest
  loading.sources = true
  errors.sources = ''
  try {
    const result = await listSources(projectId, page)
    if (request !== sourcesRequest || project.value?.id !== projectId) return
    sources.value = result
    if (!selectedSourceId.value && result.items[0]) {
      void selectSource(result.items[0].id, result.items[0].task_id)
    }
  } catch (error) {
    if (request === sourcesRequest) errors.sources = errorMessage(error)
  } finally {
    if (request === sourcesRequest) loading.sources = false
  }
}

async function loadRepositories(page = 1) {
  const projectId = project.value?.id
  if (!projectId) return
  const request = ++repositoriesRequest
  loading.repositories = true
  errors.repositories = ''
  try {
    const result = await listRepositories(projectId, page)
    if (request !== repositoriesRequest || project.value?.id !== projectId) return
    repositories.value = result
  } catch (error) {
    if (request === repositoriesRequest) errors.repositories = errorMessage(error)
  } finally {
    if (request === repositoriesRequest) loading.repositories = false
  }
}

async function registerGithubRepository(input: {
  remoteUrl: string
  localRepositoryId?: string
}) {
  const projectId = project.value?.id
  if (!projectId || loading.remote || loading.sync || loading.activity || loading.upload || loading.task) return
  loading.remote = true
  errors.remote = ''
  notice.value = ''
  try {
    const repository = await resolveGithubRepository(
      projectId, input.remoteUrl, input.localRepositoryId,
    )
    if (project.value?.id !== projectId) return
    notice.value = repository.kind === 'local_folder'
      ? `已把本地仓库“${repository.name}”关联到 ${repository.remote_url}。`
      : `已登记 GitHub 仓库“${repository.name}”，尚未导入远程文件。`
    await loadRepositories(1)
  } catch (error) {
    if (project.value?.id === projectId) errors.remote = errorMessage(error)
  } finally {
    loading.remote = false
  }
}

async function syncRegisteredGithubRepository(input: {
  repositoryId: string
  ref?: string
}) {
  const projectId = project.value?.id
  if (!projectId || loading.sync || loading.activity || loading.remote || loading.upload || loading.task) return
  loading.sync = true
  errors.sync = errors.activity = ''
  notice.value = '正在从 GitHub 读取仓库快照…'
  try {
    const result = await syncGithubRepository(projectId, input.repositoryId, input.ref)
    if (project.value?.id !== projectId) return
    const selected = [...result.items].reverse().find(
      item => item.status !== 'deleted' && item.source_id && item.task_id,
    )
    if (selected?.source_id && selected.task_id) {
      sourcesRequest++
      clearSourceSelection()
      selectedSourceId.value = selected.source_id
      selectedTaskId.value = selected.task_id
    }
    notice.value = `GitHub ${result.ref}@${result.commit_sha.slice(0, 7)} 同步完成：新增 ${result.imported_count}、复用 ${result.reused_count}、未变 ${result.unchanged_count}、重命名 ${result.renamed_count}、删除 ${result.deleted_count}、跳过 ${result.skipped_count}${result.truncated ? '；结果达到导入上限' : ''}${result.deletion_detection_complete ? '' : '；本次无法完整判断删除'}。`
    await Promise.all([loadSources(1), loadRepositories(repositories.value?.page ?? 1)])
    if (selectedSourceId.value) await refreshSource()
  } catch (error) {
    if (project.value?.id === projectId) {
      notice.value = ''
      errors.sync = errorMessage(error)
    }
  } finally {
    loading.sync = false
  }
}

async function importRegisteredGithubActivity(repositoryId: string) {
  const projectId = project.value?.id
  if (!projectId || loading.activity || loading.sync || loading.remote || loading.upload || loading.task) return
  loading.activity = true
  errors.activity = errors.sync = ''
  notice.value = '正在从 GitHub 读取最近更新的 Issue 与 Pull Request…'
  try {
    const result = await importGithubWorkItems(projectId, repositoryId)
    if (project.value?.id !== projectId) return
    const selected = [...result.items].reverse().find(
      item => item.status !== 'skipped' && item.source_id && item.task_id,
    )
    if (selected?.source_id && selected.task_id) {
      sourcesRequest++
      clearSourceSelection()
      selectedSourceId.value = selected.source_id
      selectedTaskId.value = selected.task_id
    }
    const truncatedComments = result.items.filter(item => item.comments_truncated).length
    notice.value = `GitHub Issue/PR 导入完成：新增版本 ${result.imported_count}、复用 ${result.reused_count}、跳过 ${result.skipped_count}${result.truncated ? '；结果达到 20 项上限' : ''}${truncatedComments ? `；${truncatedComments} 项评论达到导入上限` : ''}。`
    await Promise.all([loadSources(1), loadRepositories(repositories.value?.page ?? 1)])
    if (selectedSourceId.value) await refreshSource()
  } catch (error) {
    if (project.value?.id === projectId) {
      notice.value = ''
      errors.activity = errorMessage(error)
    }
  } finally {
    loading.activity = false
  }
}

async function selectSource(sourceId: string, taskId: string | null) {
  if (loading.create || loading.upload || loading.task || loading.sync || loading.activity) return
  clearSourceSelection()
  selectedSourceId.value = sourceId
  selectedTaskId.value = taskId
  await refreshSource()
}

async function refreshSource() {
  const sourceId = selectedSourceId.value
  const taskId = selectedTaskId.value
  if (!sourceId) return
  const request = ++detailRequest
  loading.detail = true
  errors.detail = errors.task = ''
  try {
    const [sourceResult, taskResult] = await Promise.all([
      getSource(sourceId), taskId ? getTask(taskId) : Promise.resolve(null),
    ])
    if (request !== detailRequest || sourceId !== selectedSourceId.value) return
    source.value = sourceResult
    task.value = taskResult
    const item = sources.value?.items.find((item) => item.id === sourceId)
    if (item) {
      item.status = sourceResult.status
      item.task_status = taskResult?.status ?? null
      item.updated_at = sourceResult.updated_at
    }
    if (taskResult?.status === 'succeeded') {
      const requests: Promise<void>[] = [loadChunks(1), loadReviews(1)]
      if (sourceResult.source_type === 'java') requests.push(loadCodeStructure())
      await Promise.all(requests)
    }
  } catch (error) {
    if (request === detailRequest) errors.detail = errorMessage(error)
  } finally {
    if (request === detailRequest) loading.detail = false
  }
}

async function loadChunks(page = 1) {
  const sourceId = selectedSourceId.value
  if (!sourceId) return
  const request = ++chunksRequest
  loading.chunks = true
  errors.chunks = ''
  try {
    const result = await listSourceChunks(sourceId, page)
    if (request === chunksRequest && sourceId === selectedSourceId.value) chunks.value = result
  } catch (error) {
    if (request === chunksRequest) errors.chunks = errorMessage(error)
  } finally {
    if (request === chunksRequest) loading.chunks = false
  }
}

async function loadCodeStructure() {
  const sourceId = selectedSourceId.value
  if (!sourceId) return
  const request = ++structureRequest
  loading.structure = true
  errors.structure = ''
  codeStructure.value = null
  try {
    const result = await getJavaCodeStructure(sourceId)
    if (request === structureRequest && sourceId === selectedSourceId.value) codeStructure.value = result
  } catch (error) {
    if (request === structureRequest) errors.structure = errorMessage(error)
  } finally {
    if (request === structureRequest) loading.structure = false
  }
}

async function uploadFiles(files: File[]) {
  const projectId = project.value?.id
  if (!projectId || !files.length || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity) return
  loading.upload = true
  errors.upload = ''
  notice.value = ''
  // Prevent an older automatic selection from replacing the upload result.
  sourcesRequest++
  clearSourceSelection()
  const failures: string[] = []
  let lastResult: SourceUploadResult | null = null
  const folderPath = files[0]?.webkitRelativePath ?? ''
  const folderRoot = folderPath.split('/').filter(Boolean)[0] ?? ''
  let repositoryId: string | undefined
  let repositoryName = ''
  if (folderRoot) {
    try {
      const repository = await resolveLocalRepository(projectId, folderRoot)
      repositoryId = repository.id
      repositoryName = repository.name
      notice.value = `已识别本地仓库“${repository.name}”，正在接收资料。`
    } catch (error) {
      errors.upload = errorMessage(error)
      loading.upload = false
      return
    }
  }
  for (const [index, file] of files.entries()) {
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
  const succeeded = files.length - failures.length
  if (repositoryId) await loadRepositories(1)
  if (lastResult) {
    selectedSourceId.value = lastResult.source_id
    selectedTaskId.value = lastResult.task_id
    notice.value = `${repositoryId ? `本地仓库“${repositoryName}”` : '单文件'}已接收 ${succeeded} / ${files.length} 份资料。相同仓库中的相同内容会复用已有资料，请查看当前解析状态。`
    await Promise.all([loadSources(1), refreshSource()])
  } else {
    notice.value = ''
  }
  if (failures.length) {
    const visibleFailures = failures.slice(0, 3).join('；')
    errors.upload = `有 ${failures.length} 份资料上传失败：${visibleFailures}${failures.length > 3 ? `；另有 ${failures.length - 3} 份未列出` : ''}`
  }
  loading.upload = false
  loading.sources = false
}

async function parseSource() {
  const taskId = selectedTaskId.value
  if (!taskId || loading.create || loading.task || loading.upload || loading.sync || loading.activity) return
  loading.task = true
  errors.task = ''
  try {
    task.value = await runTask(taskId)
    if (task.value.status === 'failed') {
      const message = task.value.error?.message
      errors.task = typeof message === 'string' ? message : '解析失败，请重试。'
    }
    await Promise.all([refreshSource(), loadSources(sources.value?.page ?? 1)])
    if (task.value?.status === 'failed') errors.task = '解析失败，请重试解析。'
  } catch (error) {
    errors.task = errorMessage(error)
  } finally {
    loading.task = false
  }
}

async function loadReviews(page = candidates.value?.page ?? 1) {
  const sourceId = selectedSourceId.value
  const projectId = project.value?.id
  if (!sourceId || !projectId) return
  const request = ++reviewsRequest
  reviewsLoading.value = true
  reviewsError.value = ''
  try {
    const [batch, status] = await Promise.all([listCandidates(projectId, sourceId, page), getExtraction(sourceId)])
    if (request !== reviewsRequest || sourceId !== selectedSourceId.value) return
    candidates.value = batch
    extraction.value = status
    if (status.task?.status === 'failed') {
      const message = status.task.error?.message
      reviewsError.value = typeof message === 'string' ? message : '提取失败，请重试。'
    }
  } catch (error) {
    if (request === reviewsRequest) reviewsError.value = errorMessage(error)
  } finally {
    if (request === reviewsRequest) reviewsLoading.value = false
  }
}

async function extractSource() {
  const sourceId = selectedSourceId.value
  if (!sourceId || extracting.value || resolving.value) return
  const action = ++reviewAction
  reviewsRequest++
  reviewsLoading.value = false
  extracting.value = true
  reviewsError.value = reviewsNotice.value = ''
  try {
    const result = await extractKnowledge(sourceId)
    if (action !== reviewAction || sourceId !== selectedSourceId.value) return
    extraction.value = result
    await loadReviews(1)
    if (action === reviewAction && result.task?.status === 'succeeded') reviewsNotice.value = `已生成 ${result.candidate_count} 条候选知识，请逐项核对证据。`
  } catch (error) {
    if (action === reviewAction) reviewsError.value = errorMessage(error)
  } finally {
    if (action === reviewAction) extracting.value = false
  }
}

async function reviewCandidate(decision: ReviewDecision) {
  if (extracting.value || resolving.value) return
  const action = ++reviewAction
  reviewsRequest++
  reviewsLoading.value = false
  resolving.value = decision.id
  reviewsError.value = reviewsNotice.value = ''
  try {
    await resolveCandidate(decision)
    if (action !== reviewAction) return
    await loadReviews()
    if (action === reviewAction) reviewsNotice.value = decision.action === 'confirm' ? '知识已写入项目图谱，审核记录已保存。' : '候选知识已拒绝，审核记录已保存。'
  } catch (error) {
    if (action === reviewAction) reviewsError.value = errorMessage(error)
  } finally {
    if (action === reviewAction) resolving.value = ''
  }
}

function openProjectGraph() {
  if (!project.value) return
  clearSearch()
  activeNav.value = 'projectGraph'
  graphType.value = ''
  graphCenter.value = ''
  void loadRealGraph('')
}

async function loadRealGraph(center = graphCenter.value) {
  const projectId = project.value?.id
  if (!projectId) return
  const request = ++graphRequest
  graphDetailRequest++
  graphLoading.value = true
  graphDetailLoading.value = false
  graphError.value = graphDetailError.value = ''
  realGraph.value = null
  realEntityDetail.value = null
  realRelationshipDetail.value = null
  graphCenter.value = center
  try {
    const result = await getProjectGraph(projectId, { centerId: center || undefined, depth: graphDepth.value, types: graphType.value })
    if (request !== graphRequest || project.value?.id !== projectId) return
    realGraph.value = result
    const selected = result.nodes.find(item => item.id === graphSelectedId.value) ?? result.nodes[0]
    graphSelectedId.value = selected?.id ?? ''
    if (selected) await selectGraphEntity(selected.id)
  } catch (error) {
    if (request === graphRequest) graphError.value = errorMessage(error)
  } finally {
    if (request === graphRequest) graphLoading.value = false
  }
}

async function selectGraphEntity(id: string) {
  if (!realGraph.value?.nodes.some(item => item.id === id)) {
    graphType.value = ''
    await loadRealGraph(id)
    return
  }
  const request = ++graphDetailRequest
  graphSelectedId.value = id
  graphSelectionKind.value = 'entity'
  graphDetailLoading.value = true
  graphDetailError.value = ''
  realEntityDetail.value = realRelationshipDetail.value = null
  try {
    const result = await getEntityDetail(id)
    if (request === graphDetailRequest) realEntityDetail.value = result
  } catch (error) {
    if (request === graphDetailRequest) graphDetailError.value = errorMessage(error)
  } finally {
    if (request === graphDetailRequest) graphDetailLoading.value = false
  }
}

async function selectGraphRelationship(id: string) {
  const request = ++graphDetailRequest
  graphSelectedId.value = id
  graphSelectionKind.value = 'relationship'
  graphDetailLoading.value = true
  graphDetailError.value = ''
  realEntityDetail.value = realRelationshipDetail.value = null
  try {
    const result = await getRelationshipDetail(id)
    if (request === graphDetailRequest) realRelationshipDetail.value = result
  } catch (error) {
    if (request === graphDetailRequest) graphDetailError.value = errorMessage(error)
  } finally {
    if (request === graphDetailRequest) graphDetailLoading.value = false
  }
}

function retryGraphDetail() {
  if (graphSelectionKind.value === 'entity') void selectGraphEntity(graphSelectedId.value)
  else void selectGraphRelationship(graphSelectedId.value)
}

function filterGraph(type: string) { graphType.value = type; void loadRealGraph('') }
function setGraphDepth(depth: number) { graphDepth.value = depth; void loadRealGraph() }

onMounted(() => {
  if (activeNav.value !== 'graph') void loadProjects()
})

const selectedNode = computed(() => nodes.find((node) => node.id === selectedId.value) ?? nodes[0])
const currentDate = computed(() => timelinePoints[timelineIndex.value]?.date ?? timelinePoints.at(-1)!.date)
const timeFilteredNodes = computed(() => nodes.filter((node) => node.validFrom <= currentDate.value))
const visibleGraphNodes = computed(() => timeFilteredNodes.value.filter((node) => visibleTypes.value.includes(node.type)))

function selectNode(id: string) {
  activeNav.value = 'graph'
  selectedId.value = id
  panelOpen.value = true
}

function changeNav(value: string) {
  if (value === 'filter') {
    if (activeNav.value === 'projectGraph') {
      ElMessage({ message: '可在项目图谱顶部按知识类型筛选。', type: 'info' })
      return
    }
    activeNav.value = 'graph'
    filterOpen.value = !filterOpen.value
    return
  }
  if (value === 'graph' && project.value) {
    openProjectGraph()
    return
  }
  if (value === 'graph' || value === 'projects' || value === 'sources' || value === 'questions') {
    activeNav.value = value
    filterOpen.value = false
    if (value !== 'graph' && !projects.value && !loading.projects) void loadProjects()
  }
}

function toggleType(type: NodeType) {
  if (visibleTypes.value.includes(type)) {
    if (visibleTypes.value.length === 1) return
    visibleTypes.value = visibleTypes.value.filter((item) => item !== type)
  } else {
    visibleTypes.value = [...visibleTypes.value, type]
  }
  ensureVisibleSelection()
}

function ensureVisibleSelection(date = currentDate.value) {
  const availableNodes = nodes.filter((node) =>
    node.validFrom <= date && visibleTypes.value.includes(node.type),
  )
  if (!availableNodes.some((node) => node.id === selectedId.value) && availableNodes[0]) {
    selectedId.value = availableNodes[0].id
  }
}

function setTimeline(value: number) {
  timelineIndex.value = value
  ensureVisibleSelection(timelinePoints[value]!.date)
}
</script>

<template>
  <div class="app-shell">
    <AppHeader :nodes="nodes" :selected-id="selectedId" :graph-active="activeNav === 'graph'" @select="selectNode" />
    <SideRail :active="activeNav === 'projectGraph' ? 'graph' : activeNav" @change="changeNav" />

    <SourceWorkspace
      v-if="activeNav === 'projects' || activeNav === 'sources'"
      :view="activeNav" :projects="projects" :project="project" :repositories="repositories" :sources="sources"
      :selected-source-id="selectedSourceId" :source="source" :task="task" :chunks="chunks"
      :code-structure="codeStructure"
      :loading="loading" :errors="errors" :notice="notice"
      @create="addProject" @select-project="selectProject" @projects-page="loadProjects"
      @repositories-page="loadRepositories" @resolve-github="registerGithubRepository" @sync-github="syncRegisteredGithubRepository" @import-github-activity="importRegisteredGithubActivity"
      @sources-page="loadSources" @select-source="selectSource" @upload="uploadFiles"
      @run="parseSource" @refresh="refreshSource" @chunks-page="loadChunks"
      @graph="openProjectGraph"
    >
      <template #reviews>
        <CandidateReview :key="selectedSourceId" :candidates="candidates" :extraction="extraction"
          :loading="reviewsLoading" :extracting="extracting" :resolving="resolving"
          :error="reviewsError" :notice="reviewsNotice"
          @extract="extractSource" @refresh="loadReviews" @resolve="reviewCandidate" />
      </template>
    </SourceWorkspace>
    <ProjectGraph v-else-if="activeNav === 'projectGraph'" :project="project" :graph="realGraph"
      :search-result="searchResult" :search-loading="searchLoading" :search-error="searchError"
      :search-rebuilding="searchRebuilding" :search-notice="searchNotice" :search-error-action="searchErrorAction"
      @search="runSearch" @rebuild-search="rebuildSemanticIndex" @clear-search="clearSearch" @retry-search="runSearch(searchQuery, searchTypes, searchMode)" @select-search-entity="openSearchEntity"
      :entity-detail="realEntityDetail" :relationship-detail="realRelationshipDetail"
      :loading="graphLoading" :detail-loading="graphDetailLoading" :error="graphError" :detail-error="graphDetailError"
      :selected-id="graphSelectedId" :center="graphCenter" :depth="graphDepth" :type-filter="graphType"
      @back="activeNav = 'sources'" @demo="activeNav = 'graph'" @refresh="loadRealGraph()"
      @select-entity="selectGraphEntity" @select-relationship="selectGraphRelationship" @neighborhood="loadRealGraph"
      @reset="loadRealGraph('')" @filter-type="filterGraph" @depth="setGraphDepth" @retry-detail="retryGraphDetail" />
    <QuestionWorkspace v-else-if="activeNav === 'questions'" :key="project?.id ?? 'no-project'"
      :projects="projects" :project="project" :projects-loading="loading.projects" :projects-error="errors.projects"
      :result="questionResult" :loading="questionLoading" :error="questionError"
      @select-project="selectProject" @retry-projects="loadProjects()" @ask="runQuestion" @retry="retryQuestion"
      @clear="clearQuestion" @open-entity="openQuestionEntity" />
    <main v-else class="atlas-main" :class="{ 'panel-collapsed': !panelOpen }">
      <section class="graph-workspace">
        <div class="workspace-title">
          <div>
            <h1>你的技术宇宙，正在成形</h1>
            <p>演示图谱 · 节点与问答使用模拟数据。真实资料可从左侧入口管理。</p>
          </div>
          <div class="workspace-stats" aria-label="图谱统计">
            <span><strong>{{ visibleGraphNodes.length }}</strong> 个节点</span>
            <span><strong>{{ edges.length }}</strong> 条关联</span>
          </div>
        </div>

        <div v-if="filterOpen" class="filter-popover">
          <div><strong>显示知识类型</strong><button type="button" @click="filterOpen = false">完成</button></div>
          <label v-for="type in allTypes" :key="type">
            <input type="checkbox" :checked="visibleTypes.includes(type)" @change="toggleType(type)" />
            <i :class="`dot-${type}`" />{{ nodeTypeLabels[type] }}
          </label>
        </div>

        <KnowledgeGraph
          :nodes="timeFilteredNodes"
          :edges="edges"
          :selected-id="selectedId"
          :visible-types="visibleTypes"
          @select="selectNode"
        />

        <TimelineBar :model-value="timelineIndex" :points="timelinePoints" @update:model-value="setTimeline" />
      </section>

      <InsightPanel
        v-if="panelOpen"
        :node="selectedNode"
        :nodes="nodes"
        :edges="edges"
        :evidences="evidences"
        @select="selectNode"
        @close="panelOpen = false"
      />

      <button v-else class="reopen-panel" type="button" @click="panelOpen = true">
        查看 {{ selectedNode.label }}
      </button>
    </main>
  </div>
</template>

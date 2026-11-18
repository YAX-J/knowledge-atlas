<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Filter, FullScreen, Minus, Plus, RefreshRight } from '@element-plus/icons-vue'
import AppHeader from './components/AppHeader.vue'
import SideRail from './components/SideRail.vue'
import KnowledgeGraph from './components/KnowledgeGraph.vue'
import InsightPanel from './components/InsightPanel.vue'
import TimelineBar from './components/TimelineBar.vue'
import SourceWorkspace from './components/SourceWorkspace.vue'
import CodeSymbolSearch from './components/CodeSymbolSearch.vue'
import RepositorySnapshots from './components/RepositorySnapshots.vue'
import SnapshotFiles from './components/SnapshotFiles.vue'
import CandidateReview from './components/CandidateReview.vue'
import ProjectGraph from './components/ProjectGraph.vue'
import KnowledgeEvolution from './components/KnowledgeEvolution.vue'
import KnowledgeRetirement from './components/KnowledgeRetirement.vue'
import QuestionWorkspace from './components/QuestionWorkspace.vue'
import ConversationsWorkspace from './components/ConversationsWorkspace.vue'
import Workbench from './components/Workbench.vue'
import AgentWorkspace from './pages/AgentWorkspace.vue'
import KnowledgeManagement from './components/KnowledgeManagement.vue'
import { useKnowledgeManagement } from './composables/useKnowledgeManagement'
import { getOverview } from './api/workspace'
import type { ProjectOverview } from './types'
import type { SourceListItem } from './api/knowledgeAtlas'
import { ApiError } from './api/client'
import { useLatestRequest } from './composables/useLatestRequest'
import { useSourceImport } from './composables/useSourceImport'
import { useCandidateReview } from './composables/useCandidateReview'
import { useProjectGraph } from './composables/useProjectGraph'
import { useKnowledgeRetirement } from './composables/useKnowledgeRetirement'
import { useKnowledgeSearch } from './composables/useKnowledgeSearch'
import { useRepositorySnapshots } from './composables/useRepositorySnapshots'
import { useEvidenceNavigation } from './composables/useEvidenceNavigation'
import { useKnowledgeEvolution } from './composables/useKnowledgeEvolution'
import { useWorkspaceRoute, type GraphSection } from './composables/useWorkspaceRoute'
import type { KnowledgeRetirement as RetirementEvent, QuestionRetrievalMode, SourceFilters } from './types'
import { isCodeSource } from './sourceLanguages'
import {
  createProject, getProject, getSource, getTask, listProjects, listSourceChunks, listSources,
  askQuestion,
  getJavaCodeStructure,
  analyzeAgentCalls,
  getCodeAnalysisContexts,
  searchCodeSymbols,
  listRepositories,
} from './api/knowledgeAtlas'
import type {
  ApiProject, ApiProjectList, ApiSource, ProcessingTask, SourceChunkList, SourceList,
  AgentCallAnalysis, JavaCodeStructure, SourceRepositoryList,
  CodeSymbolHit, CodeSymbolSearchInput, CodeSymbolSearchResult,
  CodeAnalysisContexts, CodeAnalysisSelection,
} from './api/knowledgeAtlas'
import { edges, evidences, nodes, nodeTypeLabels, timelinePoints } from './mock/data'
import type { IngestionErrors, IngestionLoading, NodeType, WorkspaceNav, QuestionAnswer } from './types'

const selectedId = ref('event-driven')
const activeNav = ref<WorkspaceNav>(import.meta.env.VITE_DATA_SOURCE === 'mock' ? 'graph' : import.meta.env.VITE_DATA_SOURCE === 'api' ? 'sources' : 'workbench')
const graphSection = ref<GraphSection>('relations')
const workbench = ref<InstanceType<typeof Workbench> | null>(null)
const focusOnly = ref(false)
const largeView = ref(false)
const sourceEntry = ref('sources')
const agentEntry = ref('agents')

const activeDeckPage = computed(() => {
  if (activeNav.value === 'sources') return sourceEntry.value
  if (activeNav.value === 'agents') return agentEntry.value
  if (activeNav.value === 'graph') return 'demo'
  if (activeNav.value !== 'projectGraph') return activeNav.value
  const entries: Record<GraphSection, string> = {
    relations: 'graph', search: 'search', evolution: 'govern', identity: 'identity', retirement: 'retirement',
  }
  return entries[graphSection.value]
})
watch(activeNav, nav => {
  if (nav !== 'sources') sourceEntry.value = 'sources'
  if (nav !== 'agents') agentEntry.value = 'agents'
  if (nav !== 'workbench' && !['graph', 'projectGraph', 'questions', 'conversations'].includes(nav)) focusOnly.value = false
})
const conversationId = ref('')
const agentRunId = ref('')
const timelineIndex = ref(timelinePoints.length - 1)
const panelOpen = ref(true)
const filterOpen = ref(false)
const allTypes = Object.keys(nodeTypeLabels) as NodeType[]
const visibleTypes = ref<NodeType[]>([...allTypes])
const projects = ref<ApiProjectList | null>(null)
const project = ref<ApiProject | null>(null)
const repositories = ref<SourceRepositoryList | null>(null)
const sources = ref<SourceList | null>(null)
const sourceFilters = ref<SourceFilters>({ query: '', type: '', status: '' })
const sourcesRequestedPage = ref(1)
const selectedSourceId = ref('')
const selectedTaskId = ref<string | null>(null)
const source = ref<ApiSource | null>(null)
const task = ref<ProcessingTask | null>(null)
const chunks = ref<SourceChunkList | null>(null)
const codeStructure = ref<JavaCodeStructure | null>(null)
const agentCallAnalysis = ref<AgentCallAnalysis | null>(null)
const analysisContexts = ref<CodeAnalysisContexts | null>(null)
const analysisContextError = ref('')
const codeSearchResult = ref<CodeSymbolSearchResult | null>(null)
const codeSearchLoading = ref(false)
const codeSearchError = ref('')
const focusedChunkId = ref('')
let codeSearchRequest = 0
let codeOpenRequest = 0
let codeSearchInput: CodeSymbolSearchInput | null = null
watch(activeNav, value => {
  if (value !== 'projectGraph') {
    clearEvolution()
  }
  if (value !== 'sources' && value !== 'projects') {
    clearCodeSearch()
    if (evidenceNavigationLoading.value) clearSourceSelection()
    else clearEvidenceNavigation()
  }
})

function clearCodeSearch() {
  codeSearchRequest++
  codeOpenRequest++
  codeSearchResult.value = null
  codeSearchLoading.value = false
  codeSearchError.value = ''
  codeSearchInput = null
}

async function runCodeSearch(input: CodeSymbolSearchInput) {
  const projectId = project.value?.id
  if (!projectId) return
  const request = ++codeSearchRequest
  codeSearchInput = input
  codeSearchLoading.value = true
  codeSearchResult.value = null
  codeSearchError.value = ''
  try {
    const result = await searchCodeSymbols(projectId, input)
    if (request === codeSearchRequest && project.value?.id === projectId) codeSearchResult.value = result
  } catch (error) {
    if (request === codeSearchRequest && project.value?.id === projectId) codeSearchError.value = errorMessage(error)
  } finally {
    if (request === codeSearchRequest) codeSearchLoading.value = false
  }
}

async function openCodeSymbol(hit: CodeSymbolHit) {
  if (loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit) return
  const projectId = project.value?.id
  clearSourceSelection()
  const request = ++codeOpenRequest
  selectedSourceId.value = hit.source_id
  selectedTaskId.value = hit.task_id
  await refreshSource()
  if (request !== codeOpenRequest || project.value?.id !== projectId) return
  if (hit.chunk_position !== null && hit.chunk_position >= 20) await loadChunks(Math.floor(hit.chunk_position / 20) + 1)
  if (request !== codeOpenRequest || selectedSourceId.value !== hit.source_id || project.value?.id !== projectId) return
  focusedChunkId.value = hit.chunk_id ?? ''
  await nextTick()
  const target = (hit.chunk_id ? document.getElementById(`source-chunk-${hit.chunk_id}`) : null)
    ?? document.getElementById('source-reader')
  target?.focus({ preventScroll: true })
  target?.scrollIntoView({ block: 'center', behavior: 'instant' })
}
const notice = ref('')
const loading = reactive<IngestionLoading>({ projects: false, create: false, repositories: false, remote: false, sync: false, activity: false, commit: false, sources: false, upload: false, detail: false, task: false, chunks: false, structure: false, agent: false })
const errors = reactive<IngestionErrors>({ projects: '', create: '', repositories: '', remote: '', sync: '', activity: '', commit: '', sources: '', upload: '', detail: '', task: '', chunks: '', structure: '', agent: '' })
const {
  snapshotRepository, snapshots, snapshotsLoading, snapshotsError, snapshotsPage, importingSnapshotId,
  filesSnapshotId, snapshotFiles, snapshotFilesLoading, snapshotFilesError, snapshotFilesPage,
  closeSnapshotFiles, loadSnapshotFilePage, openSnapshotFile, clearSnapshots, loadSnapshots, saveSnapshotCommit,
} = useRepositorySnapshots({ project, activeNav, loading, errors, notice, selectedSourceId, selectedTaskId,
  clearSourceSelection, selectSource, loadSources, refreshSource, errorMessage })
const { evidenceTarget, evidenceNavigationLoading, evidenceNavigationError, clearEvidenceNavigation, openEvidence } = useEvidenceNavigation({ project, activeNav, errors, chunks, focusedChunkId, notice, selectedSourceId, selectedTaskId,
  locked: () => changeBusy.value || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit,
  clearSourceSelection, refreshSource, errorMessage })
const { githubContinuations, registerGithubRepository, syncRegisteredGithubRepository, importRegisteredGithubActivity, uploadFiles, parseSource } = useSourceImport({
  project, repositories, sources, selectedSourceId, selectedTaskId, task, notice, loading, errors,
  locked: () => reviewBusy.value || changeBusy.value,
  prepareSource: () => { sourcesRequest++; clearSourceSelection() },
  loadSources: page => loadSources(page), loadRepositories: page => loadRepositories(page), refreshSource: () => refreshSource(), errorMessage,
})
let projectsRequest = 0
let repositoriesRequest = 0
let sourcesRequest = 0
let detailRequest = 0
let chunksRequest = 0
let structureRequest = 0
let agentCallRequest = 0
const {
  candidates, reviewFilters, extraction, reviewsLoading, extracting, resolving, reviewBusy, reviewsError, reviewsNotice,
  clearReviews, applyReviewFilters, loadReviews, extractSource, reviewCandidate, reviewCandidatesBatch,
} = useCandidateReview(project, selectedSourceId, () => clearIndexStatus(), errorMessage)
const changeBusy = ref(false)
const {
  realGraph, realEntityDetail, realRelationshipDetail, graphLoading, graphDetailLoading, graphError, graphDetailError,
  graphSelectedId, graphSelectionKind, graphCenter, graphType, graphDepth, graphValidAt,
  timeline: graphTimeline, loadGraphTimeline,
  graphBackend, neo4jSnapshot, neo4jSyncing, neo4jSyncError, selectGraphBackend, syncGraphToNeo4j,
  clearProjectGraph, loadRealGraph, selectGraphEntity, selectGraphRelationship, retryGraphDetail, filterGraph, setGraphDepth,
} = useProjectGraph(() => ({ projectId: project.value?.id, active: activeNav.value === 'projectGraph', relations: graphSection.value === 'relations' }), errorMessage,
  () => clearHistory(),
  () => { void loadHistory() })
const {
  history, knowledgeChanges, governance, governanceKind, comparison, comparisonLoading, comparisonError,
  closeComparison, compareKnowledge, evolutionLoading, evolutionError, changeNotice, clearEvolution,
  clearHistory, clearGovernance, loadHistory, loadChanges, runGovernance, proposeChange, resolveChange,
} = useKnowledgeEvolution(
  () => ({ projectId: project.value?.id, entityId: realEntityDetail.value?.entity.id, active: activeNav.value === 'projectGraph', validAt: graphValidAt.value }),
  changeBusy, { clearSearch: () => clearSearch(), loadRealGraph, selectEntityId: id => { graphSelectedId.value = id } }, errorMessage)
const {
  retirements, retirementsLoading, retirementsError, retirementError, retirementNotice,
  loadRetirements, retireKnowledge,
} = useKnowledgeRetirement(() => ({ projectId: project.value?.id, active: activeNav.value === 'projectGraph', validAt: graphValidAt.value }),
  changeBusy, errorMessage, async () => {
    clearSearch(); clearQuestion(); closeComparison()
    clearGovernance()
    clearHistory()
    graphSelectedId.value = ''; graphType.value = ''
    await Promise.all([loadRealGraph(''), loadIndexStatus()])
  })
const retirementSelection = computed(() => {
  const record = realEntityDetail.value?.entity ?? realRelationshipDetail.value?.relationship
  return record ? { kind: realEntityDetail.value ? 'entity' as const : 'relationship' as const,
    id: record.id, name: record.name, current: record.status === 'active' && !record.valid_to } : null
})
const { identity: managedIdentity, operations: managementOperations, loading: managementLoading, error: managementError,
  notice: managementNotice, refresh: refreshManagement, apply: applyManagement } = useKnowledgeManagement(
  () => ({ projectId: project.value?.id, entityId: realEntityDetail.value?.entity.id,
    active: activeNav.value === 'projectGraph', validAt: graphValidAt.value }), changeBusy, async () => {
    clearSearch(); clearQuestion(); closeComparison()
    clearGovernance()
    clearProjectGraph()
    await Promise.all([loadRealGraph(''), loadIndexStatus(), loadChanges(1), loadRetirements()])
  })
const overviewState = useLatestRequest<ProjectOverview>(errorMessage)
const railCounts = computed(() => ({
  workbench: overviewState.result.value?.pending_reviews,
  sources: sources.value?.total,
  review: overviewState.result.value?.pending_reviews,
  graph: overviewState.result.value?.entities,
  search: overviewState.result.value?.entities,
}))
async function refreshOverview() {
  const id = project.value?.id
  if (!id) return
  await overviewState.run(() => getOverview(id), () => project.value?.id === id && activeNav.value === 'workbench')
}
watch(() => [project.value?.id, activeNav.value], () => {
  overviewState.clear()
  if (activeNav.value === 'workbench' && project.value) void refreshOverview()
})
async function visitRetiredKnowledge(event: RetirementEvent) {
  if (changeBusy.value || event.project_id !== project.value?.id) return
  const projectId = project.value.id
  if (event.kind === 'entity') await setGraphTime(event.before.valid_from, event.knowledge_id)
  else {
    await setGraphTime(event.before.valid_from)
    if (project.value?.id === projectId && activeNav.value === 'projectGraph') await selectGraphRelationship(event.knowledge_id)
  }
}
async function setGraphTime(value: string, entityId = '') {
  if (changeBusy.value) return
  graphValidAt.value = value
  clearGovernance()
  closeComparison(); governanceKind.value = ''
  clearSearch()
  void loadIndexStatus()
  if (entityId) graphSelectedId.value = entityId
  graphType.value = ''
  await loadRealGraph(entityId)
}
const {
  searchResult, searchLoading, searchError, searchRebuilding, searchErrorAction, searchNotice,
  indexStatus, indexStatusLoading, indexStatusError, loadIndexStatus, clearIndexStatus,
  embeddingJob, embeddingJobError,
  clearSearch, runSearch, retrySearch, rebuildSemanticIndex,
} = useKnowledgeSearch(() => ({ projectId: project.value?.id, validAt: graphValidAt.value }), errorMessage)
const questionState = useLatestRequest<QuestionAnswer>(errorMessage)
const { result: questionResult, loading: questionLoading, error: questionError } = questionState
let questionText = ''
let questionMode: QuestionRetrievalMode = 'rrf'
let questionValidAt: string | undefined

function clearQuestion() {
  questionState.clear()
  questionText = ''
  questionMode = 'rrf'
  questionValidAt = undefined
}

async function runQuestion(question: string, mode: QuestionRetrievalMode = 'rrf', validAt?: string) {
  const projectId = project.value?.id
  if (!projectId || questionLoading.value) return
  questionText = question
  questionMode = mode
  questionValidAt = validAt
  await questionState.run(() => validAt ? askQuestion(projectId, question, mode, validAt) : askQuestion(projectId, question, mode),
    () => project.value?.id === projectId)
}

function retryQuestion() {
  if (questionText) void runQuestion(questionText, questionMode, questionValidAt)
}

async function openSearchEntity(id: string) {
  const projectId = project.value?.id
  graphSection.value = 'relations'
  await selectGraphEntity(id)
  await nextTick()
  if (project.value?.id === projectId && graphSelectedId.value === id) document.getElementById('formal-knowledge-detail')?.focus()
}

async function openQuestionEntity(id: string) {
  if (!project.value) return
  graphSection.value = 'relations'
  activeNav.value = 'projectGraph'
  clearSearch()
  graphValidAt.value = ''
  graphType.value = ''
  graphSelectedId.value = id
  void loadIndexStatus()
  await loadRealGraph(id)
  await nextTick()
  if (graphSelectedId.value === id) document.getElementById('formal-knowledge-detail')?.focus()
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return '无法确认请求结果。请检查后端服务和网络连接，刷新后重试。'
}

function clearSourceSelection() {
  clearEvidenceNavigation()
  codeOpenRequest++
  focusedChunkId.value = ''
  clearReviews()
  detailRequest++
  chunksRequest++
  structureRequest++
  agentCallRequest++
  selectedSourceId.value = ''
  selectedTaskId.value = null
  source.value = null
  task.value = null
  chunks.value = null
  codeStructure.value = null
  agentCallAnalysis.value = null
  analysisContexts.value = null; analysisContextError.value = ''
  errors.detail = errors.task = errors.chunks = errors.structure = errors.agent = ''
  loading.detail = loading.chunks = loading.structure = loading.agent = false
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
  if (reviewBusy.value || changeBusy.value || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit) return
  clearEvolution()
  conversationId.value = ''
  agentRunId.value = ''
  graphValidAt.value = ''
  clearQuestion()
  clearIndexStatus()
  clearSnapshots()
  errors.commit = ''
  clearCodeSearch()
  project.value = value
  clearSearch()
  clearProjectGraph()
  repositories.value = null
  repositoriesRequest++
  sources.value = null
  sourcesRequest++
  sourceFilters.value = { query: '', type: '', status: '' }
  sourcesRequestedPage.value = 1
  clearSourceSelection()
  errors.repositories = errors.remote = errors.sync = errors.activity = errors.sources = errors.upload = ''
  notice.value = ''
  void Promise.all([loadRepositories(1), loadSources(1)])
}

async function addProject(input: { name: string; description: string }) {
  if (loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit) return
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
  sourcesRequestedPage.value = page
  const filters = { ...sourceFilters.value }
  loading.sources = true
  errors.sources = ''
  try {
    const result = await listSources(projectId, page, 20, filters)
    if (request !== sourcesRequest || project.value?.id !== projectId) return
    const lastPage = Math.max(1, Math.ceil(result.total / result.page_size))
    if (page > lastPage) { await loadSources(lastPage); return }
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

async function filterSources(filters: SourceFilters) {
  if (reviewBusy.value || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit || loading.agent) return
  const projectId = project.value?.id
  sourceFilters.value = { ...filters }
  const applied = sourceFilters.value
  sources.value = null
  await loadSources(1)
  await nextTick()
  if (project.value?.id !== projectId || sourceFilters.value !== applied) return
  const heading = document.getElementById('source-list-title')
  heading?.focus({ preventScroll: true })
  heading?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
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

async function selectSource(sourceId: string, taskId: string | null) {
  if (reviewBusy.value || loading.create || loading.upload || loading.task || loading.sync || loading.activity || loading.commit) return
  clearSourceSelection()
  selectedSourceId.value = sourceId
  selectedTaskId.value = taskId
  await refreshSource()
}

async function openAgentReview(sourceId: string) {
  if (changeBusy.value || reviewBusy.value) return
  changeNav('sources')
  await selectSource(sourceId, null)
  await nextTick()
  if (activeNav.value === 'sources' && selectedSourceId.value === sourceId) {
    document.getElementById('candidate-title')?.focus()
  }
}

async function refreshSource(chunkPage = 1) {
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
    if (sourceResult.project_id !== project.value?.id) throw new Error('资料不属于当前项目，请重新选择资料。')
    source.value = sourceResult
    task.value = taskResult
    const item = sources.value?.items.find((item) => item.id === sourceId)
    if (item) {
      item.status = sourceResult.status
      item.task_status = taskResult?.status ?? null
      item.updated_at = sourceResult.updated_at
    }
    if (sourceResult.status === 'ready') {
      const requests: Promise<void>[] = [loadChunks(chunkPage), loadReviews(1)]
      if (isCodeSource(sourceResult.source_type)) requests.push(loadCodeStructure(), loadAnalysisContexts())
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

async function loadAnalysisContexts() {
  const id = selectedSourceId.value, captured = detailRequest
  if (!id) return
  analysisContextError.value = ''
  try {
    const result = await getCodeAnalysisContexts(id)
    if (captured === detailRequest && selectedSourceId.value === id) analysisContexts.value = result
  } catch (error) { if (captured === detailRequest && selectedSourceId.value === id) analysisContextError.value = errorMessage(error) }
}
async function runAgentCallAnalysis(strategy: 'single_step' | 'tools' | 'semantic' = 'single_step', selection: CodeAnalysisSelection = {}) {
  const sourceId = selectedSourceId.value
  if (!sourceId || loading.agent || source.value?.status !== 'ready') return
  const request = ++agentCallRequest
  loading.agent = true
  errors.agent = ''
  agentCallAnalysis.value = null
  try {
    const result = await analyzeAgentCalls(sourceId, strategy, selection)
    if (request === agentCallRequest && sourceId === selectedSourceId.value) {
      agentCallAnalysis.value = result
    }
  } catch (error) {
    if (request === agentCallRequest) errors.agent = errorMessage(error)
  } finally {
    if (request === agentCallRequest) loading.agent = false
  }
}

function openProjectGraph() {
  if (!project.value || reviewBusy.value || changeBusy.value) return
  clearSearch()
  activeNav.value = 'projectGraph'
  graphType.value = ''
  graphCenter.value = ''
  graphValidAt.value = ''
  void loadIndexStatus()
  void loadChanges(1)
  void loadRealGraph('')
}

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
  if (changeBusy.value || reviewBusy.value) return
  cancelRouteRestore()
  if (value === 'demo') { activeNav.value = 'graph'; return }
  if (value === 'review' || value === 'repositories' || value === 'code') {
    activeNav.value = 'sources'
    sourceEntry.value = value
    if (!projects.value && !loading.projects) void loadProjects()
    const target = value === 'review' ? 'candidate-title' : value === 'repositories' ? 'repository-panel-title' : 'code-search-title'
    void nextTick(() => focusDeckHeading(target, 'source-list-title'))
    return
  }
  if (value === 'notes' || value === 'agents') {
    activeNav.value = 'agents'
    agentEntry.value = value
    if (!projects.value && !loading.projects) void loadProjects()
    void nextTick(() => focusDeckHeading(value === 'notes' ? 'notes-title' : 'project-assistant-title', 'agent-workspace-title'))
    return
  }
  if (value === 'search' || value === 'govern' || value === 'identity' || value === 'retirement') {
    if (!project.value) { activeNav.value = 'sources'; return }
    const section = value === 'govern' ? 'evolution' : value
    if (activeNav.value !== 'projectGraph') openProjectGraph()
    graphSection.value = section
    if (section === 'evolution') void nextTick(() => focusDeckHeading('governance-title', 'evolution-title'))
    return
  }
  if (value === 'filter') {
    if (activeNav.value === 'projectGraph') {
      ElMessage({ message: '可在项目图谱顶部按知识类型筛选。', type: 'info' })
      return
    }
    activeNav.value = 'graph'
    filterOpen.value = !filterOpen.value
    return
  }
  if (value === 'graph') {
    graphSection.value = 'relations'
    if (project.value) openProjectGraph()
    else { activeNav.value = 'sources'; ElMessage({ message: '请先选择或创建项目，再打开真实图谱。', type: 'info' }) }
    return
  }
  if (value === 'projects' || value === 'sources' || value === 'questions' || value === 'workbench' || value === 'conversations') {
    activeNav.value = value
    if (value === 'workbench') focusOnly.value = false
    if (value === 'sources') sourceEntry.value = 'sources'
    filterOpen.value = false
    if (!projects.value && !loading.projects) void loadProjects()
    if (value === 'sources') void nextTick(() => focusDeckHeading('source-workspace-title'))
  }
}

function focusDeckHeading(id: string, fallback?: string) {
  const target = document.getElementById(id) ?? (fallback ? document.getElementById(fallback) : null)
  target?.scrollIntoView?.({ block: 'start' })
  target?.focus({ preventScroll: true })
}

function toggleFocus() {
  if (focusOnly.value) {
    focusOnly.value = false
    return
  }
  if (!['projectGraph', 'questions', 'conversations'].includes(activeNav.value)) {
    changeNav('questions')
    if (activeNav.value !== 'questions') return
  }
  focusOnly.value = true
}

async function openWorkbenchSource(item: SourceListItem) {
  if (item.project_id !== project.value?.id) return
  changeNav('sources')
  if (activeNav.value !== 'sources') return
  await selectSource(item.id, item.task_id)
  await nextTick()
  if (activeNav.value === 'sources' && sourceEntry.value === 'sources' && selectedSourceId.value === item.id) focusDeckHeading('source-reader')
}

async function searchCurrentProject(query: string) {
  if (reviewBusy.value || changeBusy.value) return
  if (!project.value) { activeNav.value = 'sources'; ElMessage({ message: '请先选择项目。', type: 'info' }); return }
  openProjectGraph()
  graphSection.value = 'search'
  await nextTick()
  await runSearch(query, '', 'bm25_source')
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

const {routeError,retryRoute,cancelRouteRestore}=useWorkspaceRoute(()=>({nav:activeNav.value,projectId:project.value?.id,
  sourceId:selectedSourceId.value || undefined,entityId:graphSelectionKind.value==='entity'?graphSelectedId.value || undefined:undefined,
  relationshipId:graphSelectionKind.value==='relationship'?graphSelectedId.value || undefined:undefined,
  validAt:graphValidAt.value || undefined,conversationId:conversationId.value || undefined,runId:agentRunId.value||undefined,section:graphSection.value}),async (route,current)=>{
  if(route.nav==='graph'){activeNav.value='graph';return}
  activeNav.value=route.nav
  if(!projects.value)await loadProjects()
  if(!current())return
  if(route.projectId && route.projectId!==project.value?.id){
    const selected=projects.value?.items.find(item=>item.id===route.projectId) ?? await getProject(route.projectId)
    if(!current())return
    selectProject(selected)
  }
  if(route.sourceId && route.sourceId!==selectedSourceId.value){
    const document=await getSource(route.sourceId)
    if(!current())return
    if(document.project_id!==project.value?.id)throw new Error('此资料不属于 URL 中的项目。')
    await selectSource(route.sourceId,null)
  }
  if(!current())return
  conversationId.value=route.conversationId ?? ''
  agentRunId.value=route.runId ?? ''
  graphSection.value=route.section ?? 'relations'
  if(route.nav==='projectGraph' && project.value){
    graphValidAt.value=route.validAt ?? ''
    graphSelectedId.value=route.entityId ?? ''
    await loadRealGraph(route.entityId ?? '')
    if(current() && route.relationshipId)await selectGraphRelationship(route.relationshipId)
    if(current())await Promise.all([loadIndexStatus(),loadChanges(1)])
  }
},()=>reviewBusy.value || changeBusy.value || loading.upload || loading.task || loading.sync || loading.activity || loading.commit)
</script>

<template>
  <div class="app-shell" :class="{ 'deck-large-view': largeView && activeNav !== 'workbench' }">
    <AppHeader :nodes="nodes" :selected-id="selectedId" :graph-active="activeNav === 'graph'" :project-name="project?.name"
      :active="activeDeckPage" :focus-only="focusOnly" @select="selectNode" @search="searchCurrentProject" @navigate="changeNav" @toggle-focus="toggleFocus">
      <template v-if="activeNav === 'workbench'">
        <button class="deck-button layout-action" type="button" @click="workbench?.resetLayout()"><RefreshRight aria-hidden="true" />重置布局</button>
        <button class="deck-button layout-action" type="button" @click="workbench?.toggleAll()">
          <Plus v-if="workbench?.allCollapsed" aria-hidden="true" /><Minus v-else aria-hidden="true" />{{ workbench?.allCollapsed ? '展开全部' : '收起全部' }}
        </button>
        <button class="deck-button layout-action" type="button" :aria-pressed="Boolean(workbench?.expanded)" @click="workbench?.toggleLargeCard()">
          <FullScreen aria-hidden="true" />{{ workbench?.expanded ? '全部模块' : '大卡片' }}
        </button>
      </template>
      <template v-else>
        <button v-if="activeNav === 'graph'" class="deck-button" type="button" :aria-pressed="filterOpen" @click="changeNav('filter')">
          <Filter aria-hidden="true" />筛选图谱
        </button>
        <button class="deck-button layout-action" type="button" :aria-pressed="largeView" @click="largeView = !largeView">
          <FullScreen aria-hidden="true" />{{ largeView ? '退出大卡片' : '大卡片' }}
        </button>
      </template>
    </AppHeader>
    <SideRail :active="activeDeckPage" :focus-only="focusOnly" :counts="railCounts" @change="changeNav" />
    <div v-if="routeError" class="route-error" role="alert">{{ routeError }} <button type="button" @click="retryRoute">重试恢复位置</button></div>

    <Workbench v-if="activeNav === 'workbench'" ref="workbench" :project="project" :projects="projects" :overview="overviewState.result.value"
      :recent-sources="sources?.items" :sources-loading="loading.sources" :sources-error="errors.sources"
      :locked="reviewBusy || changeBusy || loading.upload || loading.task || loading.sync || loading.activity || loading.commit"
      :loading="overviewState.loading.value || loading.projects" :error="overviewState.error.value || errors.projects"
      @navigate="changeNav" @select-project="selectProject" @open-source="openWorkbenchSource" @refresh="project ? refreshOverview() : loadProjects()" />
    <AgentWorkspace v-else-if="activeNav === 'agents'" :key="project?.id" :project="project" :projects="projects" :source="source" :run-id="agentRunId"
      @select-project="selectProject" @run="agentRunId=$event" @open-evidence="openEvidence"
      @open-review="openAgentReview" @open-graph="changeNav('graph')"
      @open-source="activeNav='sources';selectSource($event,null)" />
    <ConversationsWorkspace v-else-if="activeNav === 'conversations'" :project="project" :projects="projects" :projects-loading="loading.projects" :projects-error="errors.projects" :conversation-id="conversationId" @conversation="conversationId = $event" @select-project="selectProject" @retry-projects="loadProjects()" @open-entity="openQuestionEntity" @open-evidence="openEvidence" />
    <SourceWorkspace
      v-else-if="activeNav === 'projects' || activeNav === 'sources'"
      :class="{ 'review-focused': activeDeckPage === 'review' }"
      :view="activeNav" :projects="projects" :project="project" :repositories="repositories" :sources="sources"
      :source-filters="sourceFilters" :sources-requested-page="sourcesRequestedPage"
      :github-continuations="githubContinuations"
      :selected-source-id="selectedSourceId" :source="source" :task="task" :chunks="chunks"
      :code-structure="codeStructure"
      :agent-call-analysis="agentCallAnalysis"
      :analysis-contexts="analysisContexts" :analysis-context-error="analysisContextError"
      :focused-chunk-id="focusedChunkId"
      :loading="loading" :errors="errors" :notice="notice" :review-busy="reviewBusy"
      @create="addProject" @select-project="selectProject" @projects-page="loadProjects"
      @repositories-page="loadRepositories" @resolve-github="registerGithubRepository" @sync-github="syncRegisteredGithubRepository" @import-github-activity="importRegisteredGithubActivity"
      @snapshots="loadSnapshots"
      @sources-page="loadSources" @filter-sources="filterSources" @select-source="selectSource" @upload="uploadFiles"
      @run="parseSource" @refresh="refreshSource" @chunks-page="loadChunks"
      @analyze-calls="runAgentCallAnalysis"
      @graph="openProjectGraph"
    >
      <template v-if="activeNav === 'sources' && project" #source-nav>
        <nav class="source-tabs" aria-label="资料库功能">
          <button v-for="entry in [{ id: 'sources', label: '资料文件' }, { id: 'repositories', label: '来源仓库' }, { id: 'code', label: '代码结构' }, { id: 'review', label: '候选审核' }]"
            :key="entry.id" class="deck-button" type="button" :aria-current="activeDeckPage === entry.id ? 'page' : undefined"
            @click="changeNav(entry.id)">{{ entry.label }}</button>
        </nav>
      </template>
      <template #evidence-navigation>
        <section v-if="evidenceTarget" id="evidence-navigation" class="evidence-navigation" aria-label="证据原文定位" :aria-busy="evidenceNavigationLoading" tabindex="-1">
          <p v-if="evidenceNavigationLoading" role="status">正在定位证据原文分块…</p>
          <p v-if="evidenceNavigationError" class="inline-error" role="alert">{{ evidenceNavigationError }}</p>
          <button v-if="evidenceNavigationError" type="button" class="text-button" @click="evidenceTarget && openEvidence(evidenceTarget)">重试定位证据</button>
          <button type="button" class="text-button" @click="clearSourceSelection">{{ evidenceNavigationLoading ? '取消定位' : '关闭定位提示' }}</button>
        </section>
      </template>
      <template #snapshots>
        <RepositorySnapshots :repository="snapshotRepository" :snapshots="snapshots" :loading="snapshotsLoading" :error="snapshotsError" :requested-page="snapshotsPage" :importing-id="importingSnapshotId" :files-snapshot-id="filesSnapshotId"
          :locked="loading.commit || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity"
          @page="snapshotRepository && loadSnapshots(snapshotRepository, $event)" @import="saveSnapshotCommit" @files="loadSnapshotFilePage" @close="clearSnapshots" @continue="snapshotRepository && syncRegisteredGithubRepository({ repositoryId: snapshotRepository.id, ref: $event.ref, continueFromSnapshot: $event.snapshotId })">
          <template #files><SnapshotFiles :snapshot-id="filesSnapshotId" :files="snapshotFiles" :loading="snapshotFilesLoading" :error="snapshotFilesError" :requested-page="snapshotFilesPage"
            :locked="loading.commit || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity"
            @page="loadSnapshotFilePage(filesSnapshotId, $event)" @open="openSnapshotFile" @close="closeSnapshotFiles" /></template>
        </RepositorySnapshots>
      </template>
      <template #code-search>
        <CodeSymbolSearch :key="project?.id ?? 'no-project'" :repositories="repositories"
          :result="codeSearchResult" :loading="codeSearchLoading" :error="codeSearchError"
          :locked="loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit"
          @search="runCodeSearch" @clear="clearCodeSearch" @retry="codeSearchInput && runCodeSearch(codeSearchInput)" @open="openCodeSymbol" />
      </template>
      <template #reviews>
        <CandidateReview :key="selectedSourceId" :candidates="candidates" :extraction="extraction"
          :loading="reviewsLoading" :extracting="extracting" :resolving="resolving"
          :error="reviewsError" :notice="reviewsNotice" :filters="reviewFilters"
          @extract="extractSource" @refresh="loadReviews" @filter="applyReviewFilters" @resolve="reviewCandidate" @resolve-batch="reviewCandidatesBatch" @graph="openProjectGraph" />
      </template>
    </SourceWorkspace>
    <ProjectGraph v-else-if="activeNav === 'projectGraph'" :project="project" :graph="realGraph"
      :section="graphSection" @section="graphSection = $event"
      :backend="graphBackend" :neo4j-snapshot="neo4jSnapshot" :neo4j-syncing="neo4jSyncing" :neo4j-sync-error="neo4jSyncError"
      @backend="selectGraphBackend" @sync-neo4j="syncGraphToNeo4j"
      :valid-at="graphValidAt" :mutation-busy="changeBusy" @time="setGraphTime"
      :timeline="graphTimeline.result.value" :timeline-loading="graphTimeline.loading.value" :timeline-error="graphTimeline.error.value" @retry-timeline="loadGraphTimeline"
      :search-result="searchResult" :search-loading="searchLoading" :search-error="searchError"
      :search-rebuilding="searchRebuilding" :search-notice="searchNotice" :search-error-action="searchErrorAction"
      :index-status="indexStatus" :index-status-loading="indexStatusLoading" :index-status-error="indexStatusError" @inspect-index="loadIndexStatus"
      :embedding-job="embeddingJob" :embedding-job-error="embeddingJobError"
      @search="runSearch" @rebuild-search="rebuildSemanticIndex" @clear-search="clearSearch" @retry-search="retrySearch" @select-search-entity="openSearchEntity"
      :entity-detail="realEntityDetail" :relationship-detail="realRelationshipDetail"
      :loading="graphLoading" :detail-loading="graphDetailLoading" :error="graphError" :detail-error="graphDetailError"
      :selected-id="graphSelectedId" :center="graphCenter" :depth="graphDepth" :type-filter="graphType"
      @back="activeNav = 'sources'" @demo="activeNav = 'graph'" @refresh="loadRealGraph(); loadGraphTimeline()"
      @select-entity="selectGraphEntity" @select-relationship="selectGraphRelationship" @neighborhood="loadRealGraph"
      @reset="loadRealGraph('')" @filter-type="filterGraph" @depth="setGraphDepth" @retry-detail="retryGraphDetail" @open-evidence="openEvidence">
      <template #evolution>
        <div v-show="graphSection === 'identity'">
        <KnowledgeManagement :nodes="realGraph?.nodes ?? []" :selected="retirementSelection" :identity="managedIdentity" :operations="managementOperations" :retirements="retirements?.items ?? []" :changes="knowledgeChanges" :historical="Boolean(graphValidAt)" :busy="changeBusy" :loading="managementLoading" :error="managementError" :notice="managementNotice" @apply="applyManagement" @refresh="refreshManagement" />
        </div><div v-show="graphSection === 'retirement'">
        <KnowledgeRetirement :selected="retirementSelection" :records="retirements" :loading="retirementsLoading"
          :error="retirementsError" :action-error="retirementError" :notice="retirementNotice" :busy="changeBusy" :historical="Boolean(graphValidAt)"
          @retire="retireKnowledge" @page="loadRetirements" @visit="visitRetiredKnowledge" />
        </div><div v-show="graphSection === 'evolution'">
        <KnowledgeEvolution :nodes="realGraph?.nodes ?? []" :selected="realEntityDetail" :history="history"
        :changes="knowledgeChanges" :governance="governance" :history-loading="evolutionLoading.history" :changes-loading="evolutionLoading.changes"
        :governance-loading="evolutionLoading.governance" :history-error="evolutionError.history" :changes-error="evolutionError.changes"
        :governance-error="evolutionError.governance" :action-error="evolutionError.action" :notice="changeNotice" :busy="changeBusy" :historical="Boolean(graphValidAt)"
        :governance-kind="governanceKind" :comparison="comparison" :comparison-loading="comparisonLoading" :comparison-error="comparisonError"
        @history="loadHistory" @changes="loadChanges" @inspect="runGovernance" @propose="proposeChange" @resolve="resolveChange"
        @compare="compareKnowledge" @close-comparison="closeComparison" @retry-comparison="compareKnowledge()"
        @open-evidence="openEvidence" @open-entity="openQuestionEntity" @visit-version="(id, at) => setGraphTime(at, id)" /></div></template>
    </ProjectGraph>
    <QuestionWorkspace v-else-if="activeNav === 'questions'" :key="project?.id ?? 'no-project'"
      :projects="projects" :project="project" :projects-loading="loading.projects" :projects-error="errors.projects"
      :result="questionResult" :loading="questionLoading" :error="questionError"
      @select-project="selectProject" @retry-projects="loadProjects()" @ask="runQuestion" @retry="retryQuestion"
      @clear="clearQuestion" @open-entity="openQuestionEntity" @open-evidence="openEvidence" />
    <main v-else class="atlas-main" :class="{ 'panel-collapsed': !panelOpen }">
      <section class="graph-workspace">
        <div class="workspace-title">
          <div>
            <h1>独立演示图谱</h1>
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

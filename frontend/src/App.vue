<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
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
import KnowledgeManagement from './components/KnowledgeManagement.vue'
import { useKnowledgeManagement } from './composables/useKnowledgeManagement'
import { getOverview } from './api/workspace'
import type { ProjectOverview } from './types'
import { ApiError } from './api/client'
import { useLatestRequest } from './composables/useLatestRequest'
import { useSourceImport } from './composables/useSourceImport'
import { useCandidateReview } from './composables/useCandidateReview'
import { useProjectGraph } from './composables/useProjectGraph'
import { useKnowledgeRetirement } from './composables/useKnowledgeRetirement'
import { useKnowledgeSearch } from './composables/useKnowledgeSearch'
import type { GovernanceKind, KnowledgeRetirement as RetirementEvent, QuestionRetrievalMode, SourceFilters } from './types'
import { isCodeSource } from './sourceLanguages'
import {
  createProject, getSource, getTask, listProjects, listSourceChunks, listSources,
  getEntityDetail, askQuestion,
  getKnowledgeHistory, inspectGovernance, listKnowledgeChanges, proposeKnowledgeChange, resolveKnowledgeChange,
  getJavaCodeStructure, getProjectSourceChunk,
  analyzeAgentCalls,
  searchCodeSymbols,
  listRepositorySnapshots, listSnapshotFiles, importSnapshotCommit,
  listRepositories,
} from './api/knowledgeAtlas'
import type {
  ApiProject, ApiProjectList, ApiSource, ProcessingTask, SourceChunkList, SourceList,
  AgentCallAnalysis, JavaCodeStructure, SourceRepositoryList,
  CodeSymbolHit, CodeSymbolSearchInput, CodeSymbolSearchResult,
  RepositorySnapshotList, RepositorySnapshotFileList, RepositorySnapshotFile, SourceRepository,
} from './api/knowledgeAtlas'
import { edges, evidences, nodes, nodeTypeLabels, timelinePoints } from './mock/data'
import type { GovernanceResult, KnowledgeChangeInput, KnowledgeChangeList, KnowledgeHistory } from './types'
import type { EvidenceLocator, IngestionErrors, IngestionLoading, NodeType, WorkspaceNav, EntityDetail, QuestionAnswer } from './types'

const selectedId = ref('event-driven')
const activeNav = ref<WorkspaceNav>(import.meta.env.VITE_DATA_SOURCE === 'mock' ? 'graph' : import.meta.env.VITE_DATA_SOURCE === 'api' ? 'sources' : 'workbench')
const timelineIndex = ref(timelinePoints.length - 1)
const panelOpen = ref(true)
const filterOpen = ref(false)
const allTypes = Object.keys(nodeTypeLabels) as NodeType[]
const visibleTypes = ref<NodeType[]>([...allTypes])
const projects = ref<ApiProjectList | null>(null)
const project = ref<ApiProject | null>(null)
const repositories = ref<SourceRepositoryList | null>(null)
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
const codeSearchResult = ref<CodeSymbolSearchResult | null>(null)
const codeSearchLoading = ref(false)
const codeSearchError = ref('')
const focusedChunkId = ref('')
const evidenceTarget = ref<EvidenceLocator | null>(null)
const evidenceNavigationLoading = ref(false)
const evidenceNavigationError = ref('')
let evidenceNavigationRequest = 0

function clearEvidenceNavigation() {
  evidenceNavigationRequest++
  evidenceTarget.value = null
  evidenceNavigationLoading.value = false
  evidenceNavigationError.value = ''
}

async function openEvidence(locator: EvidenceLocator) {
  if (!project.value || changeBusy.value || loading.create || loading.upload || loading.task || loading.remote || loading.sync || loading.activity || loading.commit) return
  const projectId = project.value.id
  clearSourceSelection()
  notice.value = ''
  evidenceTarget.value = { source_id: locator.source_id, chunk_id: locator.chunk_id }
  evidenceNavigationLoading.value = true
  activeNav.value = 'sources'
  const request = ++evidenceNavigationRequest
  const current = () => request === evidenceNavigationRequest && project.value?.id === projectId
  try {
    const chunk = await getProjectSourceChunk(projectId, locator.source_id, locator.chunk_id)
    if (!current()) return
    selectedSourceId.value = chunk.source_id
    selectedTaskId.value = null // Evidence reads do not require a surviving parsing task.
    await refreshSource(Math.floor(chunk.position / 20) + 1)
    if (!current()) return
    if (!chunks.value?.items.some(item => item.id === chunk.id)) {
      evidenceNavigationError.value = errors.detail || errors.chunks || '证据分块未能在当前解析结果中定位，请刷新资料后重试。'
      return
    }
    focusedChunkId.value = chunk.id
    await nextTick()
    if (!current()) return
    const target = document.getElementById(`source-chunk-${chunk.id}`)
    if (!target) {
      evidenceNavigationError.value = '当前资料尚不能展示此分块，请检查解析状态后重试。'
      return
    }
    clearEvidenceNavigation()
    notice.value = `已定位证据原文第 ${chunk.start_line}–${chunk.end_line} 行。`
    target.focus({ preventScroll: true })
    target.scrollIntoView({ block: 'center', behavior: 'instant' })
  } catch (error) {
    if (current()) evidenceNavigationError.value = errorMessage(error)
  } finally {
    if (current()) {
      evidenceNavigationLoading.value = false
      if (evidenceNavigationError.value) {
        await nextTick()
        if (current()) document.getElementById('evidence-navigation')?.focus()
      }
    }
  }
}
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
const {
  realGraph, realEntityDetail, realRelationshipDetail, graphLoading, graphDetailLoading, graphError, graphDetailError,
  graphSelectedId, graphCenter, graphType, graphDepth, graphValidAt,
  clearProjectGraph, loadRealGraph, selectGraphEntity, selectGraphRelationship, retryGraphDetail, filterGraph, setGraphDepth,
} = useProjectGraph(() => ({ projectId:project.value?.id, active:activeNav.value === 'projectGraph' }), errorMessage,
  () => { historyRequest++; history.value = null; evolutionLoading.history = false; evolutionError.history = '' },
  () => { void loadHistory() })
const history = ref<KnowledgeHistory | null>(null)
const knowledgeChanges = ref<KnowledgeChangeList | null>(null)
const governance = ref<GovernanceResult | null>(null)
const governanceKind = ref<GovernanceKind | ''>('')
const comparisonState = useLatestRequest<EntityDetail[]>(errorMessage)
const { result: comparison, loading: comparisonLoading, error: comparisonError } = comparisonState
let comparisonIds: string[] = []
function closeComparison() { comparisonState.clear(); comparisonIds = [] }
async function compareKnowledge(ids = comparisonIds) {
  const projectId = project.value?.id
  const unique = [...new Set(ids)]
  if (!projectId || changeBusy.value || unique.length !== 2) return
  comparisonIds = unique
  await comparisonState.run(async () => {
    const details = await Promise.all(unique.map(id => getEntityDetail(id)))
    if (details.some((detail, index) => detail.entity.project_id !== projectId || detail.entity.id !== unique[index])) {
      throw new Error('Comparison context changed')
    }
    return details
  }, () => project.value?.id === projectId && activeNav.value === 'projectGraph')
  await nextTick()
  if (project.value?.id === projectId && comparison.value?.every((detail, index) => detail.entity.id === unique[index])) {
    const panel = document.getElementById('knowledge-comparison')
    panel?.focus({ preventScroll: true }); panel?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
  }
}
const evolutionLoading = reactive({ history: false, changes: false, governance: false })
const evolutionError = reactive({ history: '', changes: '', governance: '', action: '' })
const changeBusy = ref(false)
const changeNotice = ref('')
const {
  retirements, retirementsLoading, retirementsError, retirementError, retirementNotice,
  loadRetirements, retireKnowledge,
} = useKnowledgeRetirement(() => ({ projectId: project.value?.id, active: activeNav.value === 'projectGraph', validAt: graphValidAt.value }),
  changeBusy, errorMessage, async () => {
    clearSearch(); clearQuestion(); closeComparison()
    governanceRequest++; governance.value = null; evolutionLoading.governance = false
    historyRequest++; history.value = null
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
    governanceRequest++; governance.value = null
    clearProjectGraph()
    await Promise.all([loadRealGraph(''), loadIndexStatus(), loadChanges(1), loadRetirements()])
  })
const overviewState = useLatestRequest<ProjectOverview>(errorMessage)
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
let historyRequest = 0
let changesRequest = 0
let governanceRequest = 0

function clearEvolution() {
  historyRequest++; changesRequest++; governanceRequest++
  history.value = null; knowledgeChanges.value = null; governance.value = null
  evolutionLoading.history = evolutionLoading.changes = evolutionLoading.governance = false
  evolutionError.history = evolutionError.changes = evolutionError.governance = evolutionError.action = ''
  changeNotice.value = ''
  closeComparison(); governanceKind.value = ''
}

async function loadHistory() {
  const projectId = project.value?.id, entityId = realEntityDetail.value?.entity.id
  const request = ++historyRequest
  history.value = null; evolutionError.history = ''
  if (!projectId || !entityId) { evolutionLoading.history = false; return }
  evolutionLoading.history = true
  try {
    const result = await getKnowledgeHistory(projectId, entityId)
    if (request === historyRequest && project.value?.id === projectId) history.value = result
  } catch (error) { if (request === historyRequest) evolutionError.history = errorMessage(error) }
  finally { if (request === historyRequest) evolutionLoading.history = false }
}

async function loadChanges(page = 1) {
  const projectId = project.value?.id
  if (!projectId) return
  const request = ++changesRequest
  evolutionLoading.changes = true; evolutionError.changes = ''
  try {
    const result = await listKnowledgeChanges(projectId, page)
    if (request === changesRequest && project.value?.id === projectId) knowledgeChanges.value = result
  } catch (error) { if (request === changesRequest) evolutionError.changes = errorMessage(error) }
  finally { if (request === changesRequest) evolutionLoading.changes = false }
}

async function runGovernance(kind = governanceKind.value) {
  const projectId = project.value?.id
  if (!projectId || changeBusy.value) return
  const request = ++governanceRequest
  governanceKind.value = kind
  closeComparison()
  governance.value = null; evolutionLoading.governance = true; evolutionError.governance = ''
  try {
    const result = await inspectGovernance(projectId, kind)
    if (request === governanceRequest && project.value?.id === projectId) governance.value = result
  } catch (error) { if (request === governanceRequest) evolutionError.governance = errorMessage(error) }
  finally { if (request === governanceRequest) evolutionLoading.governance = false }
}

async function proposeChange(input: KnowledgeChangeInput) {
  const projectId = project.value?.id
  if (!projectId || changeBusy.value || graphValidAt.value) return
  changeBusy.value = true; evolutionError.action = ''; changeNotice.value = ''
  try {
    await proposeKnowledgeChange(projectId, input)
    if (project.value?.id !== projectId) return
    changeNotice.value = '建议已保存，尚未改变正式知识。请核对原文后单独确认。'
    await loadChanges(1)
  } catch (error) { if (project.value?.id === projectId) evolutionError.action = errorMessage(error) }
  finally { changeBusy.value = false }
}

async function resolveChange(id: string, action: 'confirm' | 'reject') {
  const projectId = project.value?.id
  if (!projectId || changeBusy.value || graphValidAt.value) return
  changeBusy.value = true; evolutionError.action = ''; changeNotice.value = ''
  try {
    const result = await resolveKnowledgeChange(projectId, id, action)
    if (project.value?.id !== projectId) return
    changeNotice.value = action === 'reject' ? '建议已拒绝，知识保持不变。' : '建议已确认，审核前后快照已保存。'
    clearSearch()
    governanceRequest++; governance.value = null; evolutionLoading.governance = false
    closeComparison()
    if (action === 'confirm' && result.kind === 'SUPERSEDES') graphSelectedId.value = result.new_entity_id
    await Promise.all([loadChanges(knowledgeChanges.value?.page ?? 1), loadRealGraph('')])
  } catch (error) { if (project.value?.id === projectId) evolutionError.action = errorMessage(error) }
  finally { changeBusy.value = false }
}

async function setGraphTime(value: string, entityId = '') {
  if (changeBusy.value) return
  graphValidAt.value = value
  governanceRequest++; governance.value = null; evolutionLoading.governance = false
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

function clearQuestion() {
  questionState.clear()
  questionText = ''
  questionMode = 'rrf'
}

async function runQuestion(question: string, mode: QuestionRetrievalMode = 'rrf') {
  const projectId = project.value?.id
  if (!projectId || questionLoading.value) return
  questionText = question
  questionMode = mode
  await questionState.run(() => askQuestion(projectId, question, mode), () => project.value?.id === projectId)
}

function retryQuestion() {
  if (questionText) void runQuestion(questionText, questionMode)
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
      if (isCodeSource(sourceResult.source_type)) requests.push(loadCodeStructure())
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

async function runAgentCallAnalysis(strategy: 'single_step' | 'tools' | 'semantic' = 'single_step') {
  const sourceId = selectedSourceId.value
  if (!sourceId || loading.agent || source.value?.status !== 'ready') return
  const request = ++agentCallRequest
  loading.agent = true
  errors.agent = ''
  agentCallAnalysis.value = null
  try {
    const result = await analyzeAgentCalls(sourceId, strategy)
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
  if (changeBusy.value || reviewBusy.value) return
  if (value === 'demo') { activeNav.value = 'graph'; return }
  if (value === 'review') {
    activeNav.value = 'sources'
    void nextTick(() => { const target = document.getElementById('candidate-title'); target?.scrollIntoView({ block: 'start' }); target?.focus() })
    return
  }
  if (value === 'search' || value === 'govern') {
    if (!project.value) { activeNav.value = 'sources'; return }
    openProjectGraph()
    void nextTick(() => document.getElementById(value === 'search' ? 'project-knowledge-query' : 'knowledge-management-title')?.focus())
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
    if (project.value) openProjectGraph()
    else { activeNav.value = 'sources'; ElMessage({ message: '请先选择或创建项目，再打开真实图谱。', type: 'info' }) }
    return
  }
  if (value === 'projects' || value === 'sources' || value === 'questions' || value === 'workbench' || value === 'conversations') {
    activeNav.value = value
    filterOpen.value = false
    if (!projects.value && !loading.projects) void loadProjects()
  }
}
async function searchCurrentProject(query: string) {
  if (reviewBusy.value || changeBusy.value) return
  if (!project.value) { activeNav.value = 'sources'; ElMessage({ message: '请先选择项目。', type: 'info' }); return }
  openProjectGraph()
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
</script>

<template>
  <div class="app-shell">
    <AppHeader :nodes="nodes" :selected-id="selectedId" :graph-active="activeNav === 'graph'" :project-name="project?.name" @select="selectNode" @search="searchCurrentProject" />
    <SideRail :active="activeNav === 'projectGraph' ? 'graph' : activeNav" @change="changeNav" />

    <Workbench v-if="activeNav === 'workbench'" :project="project" :projects="projects" :overview="overviewState.result.value" :loading="overviewState.loading.value || loading.projects" :error="overviewState.error.value || errors.projects" @navigate="changeNav" @select-project="selectProject" @refresh="project ? refreshOverview() : loadProjects()" />
    <ConversationsWorkspace v-else-if="activeNav === 'conversations'" :project="project" :projects="projects" :projects-loading="loading.projects" :projects-error="errors.projects" @select-project="selectProject" @retry-projects="loadProjects()" @open-entity="openQuestionEntity" @open-evidence="openEvidence" />
    <SourceWorkspace
      v-else-if="activeNav === 'projects' || activeNav === 'sources'"
      :view="activeNav" :projects="projects" :project="project" :repositories="repositories" :sources="sources"
      :source-filters="sourceFilters" :sources-requested-page="sourcesRequestedPage"
      :github-continuations="githubContinuations"
      :selected-source-id="selectedSourceId" :source="source" :task="task" :chunks="chunks"
      :code-structure="codeStructure"
      :agent-call-analysis="agentCallAnalysis"
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
      :valid-at="graphValidAt" :mutation-busy="changeBusy" @time="setGraphTime"
      :search-result="searchResult" :search-loading="searchLoading" :search-error="searchError"
      :search-rebuilding="searchRebuilding" :search-notice="searchNotice" :search-error-action="searchErrorAction"
      :index-status="indexStatus" :index-status-loading="indexStatusLoading" :index-status-error="indexStatusError" @inspect-index="loadIndexStatus"
      :embedding-job="embeddingJob" :embedding-job-error="embeddingJobError"
      @search="runSearch" @rebuild-search="rebuildSemanticIndex" @clear-search="clearSearch" @retry-search="retrySearch" @select-search-entity="openSearchEntity"
      :entity-detail="realEntityDetail" :relationship-detail="realRelationshipDetail"
      :loading="graphLoading" :detail-loading="graphDetailLoading" :error="graphError" :detail-error="graphDetailError"
      :selected-id="graphSelectedId" :center="graphCenter" :depth="graphDepth" :type-filter="graphType"
      @back="activeNav = 'sources'" @demo="activeNav = 'graph'" @refresh="loadRealGraph()"
      @select-entity="selectGraphEntity" @select-relationship="selectGraphRelationship" @neighborhood="loadRealGraph"
      @reset="loadRealGraph('')" @filter-type="filterGraph" @depth="setGraphDepth" @retry-detail="retryGraphDetail" @open-evidence="openEvidence">
      <template #evolution>
        <KnowledgeManagement :nodes="realGraph?.nodes ?? []" :selected="retirementSelection" :identity="managedIdentity" :operations="managementOperations" :retirements="retirements?.items ?? []" :changes="knowledgeChanges" :historical="Boolean(graphValidAt)" :busy="changeBusy" :loading="managementLoading" :error="managementError" :notice="managementNotice" @apply="applyManagement" @refresh="refreshManagement" />
        <KnowledgeRetirement :selected="retirementSelection" :records="retirements" :loading="retirementsLoading"
          :error="retirementsError" :action-error="retirementError" :notice="retirementNotice" :busy="changeBusy" :historical="Boolean(graphValidAt)"
          @retire="retireKnowledge" @page="loadRetirements" @visit="visitRetiredKnowledge" />
        <KnowledgeEvolution :nodes="realGraph?.nodes ?? []" :selected="realEntityDetail" :history="history"
        :changes="knowledgeChanges" :governance="governance" :history-loading="evolutionLoading.history" :changes-loading="evolutionLoading.changes"
        :governance-loading="evolutionLoading.governance" :history-error="evolutionError.history" :changes-error="evolutionError.changes"
        :governance-error="evolutionError.governance" :action-error="evolutionError.action" :notice="changeNotice" :busy="changeBusy" :historical="Boolean(graphValidAt)"
        :governance-kind="governanceKind" :comparison="comparison" :comparison-loading="comparisonLoading" :comparison-error="comparisonError"
        @history="loadHistory" @changes="loadChanges" @inspect="runGovernance" @propose="proposeChange" @resolve="resolveChange"
        @compare="compareKnowledge" @close-comparison="closeComparison" @retry-comparison="compareKnowledge()"
        @open-evidence="openEvidence" @open-entity="openQuestionEntity" @visit-version="(id, at) => setGraphTime(at, id)" /></template>
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

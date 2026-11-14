import { effectScope, reactive, ref } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useCandidateReview } from '../src/composables/useCandidateReview'
import { useProjectGraph } from '../src/composables/useProjectGraph'
import { useSourceImport } from '../src/composables/useSourceImport'
import * as api from '../src/api/knowledgeAtlas'
import { project } from './fixtures'
import type { CandidateList, ProcessingTask, SourceList, SourceRepositoryList, SourceUploadResult } from '../src/api/knowledgeAtlas'
import type { EntityDetail, GraphTimeline, IngestionErrors, IngestionLoading, Neo4jSnapshot, ProjectGraphData } from '../src/types'

vi.mock('../src/api/knowledgeAtlas', () => ({
  getEntityDetail:vi.fn(), getRelationshipDetail:vi.fn(), getProjectGraph:vi.fn(), getGraphTimeline:vi.fn(), getNeo4jGraph:vi.fn(), syncNeo4jGraph:vi.fn(),
  extractKnowledge:vi.fn(), getExtraction:vi.fn(), listCandidates:vi.fn(), resolveCandidate:vi.fn(), resolveCandidatesBatch:vi.fn(),
  importGithubWorkItems:vi.fn(), resolveGithubRepository:vi.fn(), resolveLocalRepository:vi.fn(), syncGithubRepository:vi.fn(),
  uploadSource:vi.fn(), runTask:vi.fn(),
}))
const scopes: ReturnType<typeof effectScope>[] = []
function scoped<T>(run: () => T) { const scope=effectScope(); scopes.push(scope); return {scope,state:scope.run(run)!} }
function deferred<T>() { let resolve!: (value:T)=>void; const promise=new Promise<T>(yes=>{resolve=yes});return {promise,resolve} }
const empty: CandidateList={items:[],total:0,page:1,page_size:20}
const node = { id:'entity',candidate_id:'candidate',project_id:project.id,type:'Decision',name:'Storage',summary:'Reviewed',confidence:.9,
  status:'active',valid_from:project.created_at,valid_to:null,created_at:project.created_at,updated_at:project.created_at,evidence_count:1 }
const detail:EntityDetail={entity:node,evidence:[],relationships:[],truncated:false}
const graph:ProjectGraphData={nodes:[node],edges:[],truncated:false}
beforeEach(()=>{
  vi.resetAllMocks()
  vi.mocked(api.getProjectGraph).mockResolvedValue(graph)
  vi.mocked(api.getGraphTimeline).mockResolvedValue({ instants: [], truncated: false })
  vi.mocked(api.getEntityDetail).mockResolvedValue(detail)
  vi.mocked(api.listCandidates).mockResolvedValue(empty)
  vi.mocked(api.getExtraction).mockResolvedValue({task:null,candidate_count:0})
})

it('updates timeline stops on project changes and discards late responses', async () => {
  const context = reactive({ projectId: project.id, active: true, relations: true })
  const old = deferred<GraphTimeline>()
  const current = { instants: ['2026-06-01T00:00:00Z'], truncated: false }
  vi.mocked(api.getGraphTimeline).mockReturnValueOnce(old.promise).mockResolvedValue(current)
  const { state } = scoped(() => useProjectGraph(() => ({ ...context }), String, vi.fn(), vi.fn()))
  context.projectId = 'other'
  await Promise.resolve()
  old.resolve({ instants: ['2026-04-01T00:00:00Z'], truncated: false })
  await Promise.resolve()
  expect(state.timeline.result.value).toEqual(current)
  state.graphValidAt.value = current.instants[0]!
  expect(api.getGraphTimeline).toHaveBeenCalledTimes(2)
  context.relations = false
  expect(state.timeline.result.value).toBeNull()
})
afterEach(()=>{scopes.splice(0).forEach(scope=>scope.stop())})

it('fences graph and detail replies across project round trips, time changes and disposal',async()=>{
  const context=reactive({projectId:project.id as string|undefined,active:true})
  const clear=vi.fn(),loaded=vi.fn()
  const {state,scope}=scoped(()=>useProjectGraph(()=>({...context}),String,clear,loaded))
  const old=deferred<ProjectGraphData>()
  vi.mocked(api.getProjectGraph).mockReturnValueOnce(old.promise)
  const pending=state.loadRealGraph()
  context.projectId='other';context.projectId=project.id
  await state.loadRealGraph()
  old.resolve({...graph,nodes:[{...node,id:'stale'}]});await pending
  expect(state.realGraph.value).toEqual(graph)
  const oldDetail=deferred<EntityDetail>()
  vi.mocked(api.getEntityDetail).mockReturnValueOnce(oldDetail.promise)
  const selecting=state.selectGraphEntity(node.id)
  state.graphValidAt.value='2026-10-01T00:00:00Z'
  oldDetail.resolve(detail);await selecting
  expect(state.realEntityDetail.value).toBeNull()
  await state.loadRealGraph()
  expect(api.getEntityDetail).toHaveBeenLastCalledWith(node.id,state.graphValidAt.value)
  const late=deferred<ProjectGraphData>()
  vi.mocked(api.getProjectGraph).mockReturnValueOnce(late.promise)
  const final=state.loadRealGraph();scope.stop();late.resolve(graph);await final
  expect(state.realGraph.value).toBeNull()
  await state.loadRealGraph()
  expect(api.getProjectGraph).toHaveBeenCalledTimes(4)
})

it('supports graph retry, relationship selection, type/depth and outside-canvas navigation',async()=>{
  const {state}=scoped(()=>useProjectGraph(()=>({projectId:project.id,active:true}),String,vi.fn(),vi.fn()))
  vi.mocked(api.getProjectGraph).mockRejectedValueOnce(new Error('offline'))
  await state.loadRealGraph();expect(state.graphError.value).toContain('offline')
  await state.selectGraphEntity(node.id)
  expect(state.graphCenter.value).toBe(node.id)
  const edge={...node,id:'edge',source_id:'entity',target_id:'second'}
  vi.mocked(api.getRelationshipDetail).mockRejectedValueOnce(new Error('detail unavailable')).mockResolvedValue({relationship:edge,evidence:[]})
  await state.selectGraphRelationship(edge.id)
  expect(state.graphDetailError.value).toContain('detail unavailable')
  state.retryGraphDetail();await Promise.resolve();await Promise.resolve()
  expect(state.realRelationshipDetail.value?.relationship.id).toBe('edge')
  state.filterGraph('Decision');state.setGraphDepth(2)
  await Promise.resolve();await Promise.resolve()
  expect(api.getProjectGraph).toHaveBeenLastCalledWith(project.id,expect.objectContaining({depth:2,types:'Decision'}))
})

it('uses the Neo4j snapshot time for detail reads and reloads the graph after an explicit sync', async () => {
  const context = reactive({ projectId: project.id, active: true, relations: true })
  const { state } = scoped(() => useProjectGraph(() => ({ ...context }), String, vi.fn(), vi.fn()))
  const first = { valid_at: '2026-11-10T02:00:00.123456Z', node_count: 1, edge_count: 0 }
  const refreshed = { ...first, valid_at: '2026-11-13T02:00:00.654321Z', node_count: 2 }
  const edge = { ...node, id: 'edge', source_id: node.id, target_id: 'second' }
  vi.mocked(api.getNeo4jGraph).mockResolvedValueOnce({ ...graph, ...first }).mockResolvedValue({ ...graph, ...refreshed })
  vi.mocked(api.getRelationshipDetail).mockResolvedValue({ relationship: edge, evidence: [] })
  vi.mocked(api.syncNeo4jGraph).mockResolvedValue(refreshed)

  state.graphValidAt.value = project.created_at
  state.selectGraphBackend('neo4j')
  await vi.waitFor(() => expect(state.graphLoading.value).toBe(false))
  expect(api.syncNeo4jGraph).not.toHaveBeenCalled()
  expect(api.getProjectGraph).not.toHaveBeenCalled()
  expect(api.getEntityDetail).toHaveBeenLastCalledWith(node.id, first.valid_at)
  await state.selectGraphRelationship(edge.id)
  expect(api.getRelationshipDetail).toHaveBeenCalledWith(edge.id, first.valid_at)

  await state.syncGraphToNeo4j()
  expect(api.syncNeo4jGraph).toHaveBeenCalledOnce()
  expect(state.neo4jSnapshot.value).toEqual(refreshed)
  expect(api.getEntityDetail).toHaveBeenLastCalledWith(node.id, refreshed.valid_at)
  context.relations = false
  await vi.waitFor(() => expect(state.graphLoading.value).toBe(false))
  expect(state.graphBackend.value).toBe('postgresql')
  expect(state.neo4jSnapshot.value).toBeNull()
  expect(api.getProjectGraph).toHaveBeenCalledOnce()
})

it('discards a late Neo4j sync after switching projects and lets a failed sync be retried explicitly', async () => {
  const context = reactive({ projectId: project.id, active: true })
  const { state } = scoped(() => useProjectGraph(() => ({ ...context }), String, vi.fn(), vi.fn()))
  const snapshot = { valid_at: project.created_at, node_count: 1, edge_count: 0 }
  vi.mocked(api.getNeo4jGraph).mockResolvedValue({ ...graph, ...snapshot })
  state.selectGraphBackend('neo4j')
  await vi.waitFor(() => expect(state.graphLoading.value).toBe(false))
  vi.mocked(api.syncNeo4jGraph).mockRejectedValueOnce(new Error('sync failed'))
  await state.syncGraphToNeo4j()
  expect(state.neo4jSyncError.value).toContain('sync failed')
  expect(state.neo4jSnapshot.value).toEqual(snapshot)

  const pending = deferred<Neo4jSnapshot>()
  vi.mocked(api.syncNeo4jGraph).mockReturnValueOnce(pending.promise)
  const syncing = state.syncGraphToNeo4j()
  await state.syncGraphToNeo4j()
  expect(api.syncNeo4jGraph).toHaveBeenCalledTimes(2)
  context.projectId = 'other'
  pending.resolve(snapshot)
  await syncing
  expect(state.graphBackend.value).toBe('postgresql')
  expect(state.neo4jSnapshot.value).toBeNull()
  expect(state.neo4jSyncing.value).toBe(false)
  expect(api.getNeo4jGraph).toHaveBeenCalledOnce()
})

it('isolates review extraction and list replies after source round trips and unmount',async()=>{
  const projectRef=ref({...project}),source=ref('first'),index=vi.fn()
  const {state,scope}=scoped(()=>useCandidateReview(projectRef,source,index,String))
  const old=deferred<CandidateList>()
  vi.mocked(api.listCandidates).mockReturnValueOnce(old.promise)
  const pending=state.loadReviews()
  source.value='second';source.value='first'
  await state.loadReviews();old.resolve({...empty,total:30});await pending
  expect(state.candidates.value?.total).toBe(0)
  const extraction=deferred<api.ExtractionResult>()
  vi.mocked(api.extractKnowledge).mockReturnValueOnce(extraction.promise)
  const extracting=state.extractSource()
  await state.extractSource();expect(api.extractKnowledge).toHaveBeenCalledTimes(1)
  scope.stop();extraction.resolve({task:null,candidate_count:8});await extracting
  expect(state.extraction.value).toBeNull()
  await state.loadReviews();expect(api.listCandidates).toHaveBeenCalledTimes(2)
})

it('keeps review pagination/filter semantics and clears index state only on confirmed server outcomes',async()=>{
  const index=vi.fn()
  const {state}=scoped(()=>useCandidateReview(ref({...project}),ref('source'),index,String))
  vi.mocked(api.listCandidates).mockResolvedValueOnce(empty)
  await state.loadReviews(3)
  expect(api.listCandidates).toHaveBeenLastCalledWith(project.id,'source',1,{status:'',kind:'',query:''})
  await state.applyReviewFilters({status:'pending',kind:'entity',query:'Storage'})
  expect(api.listCandidates).toHaveBeenLastCalledWith(project.id,'source',1,{status:'pending',kind:'entity',query:'Storage'})
  vi.mocked(api.resolveCandidate).mockRejectedValueOnce(new Error('unknown result'))
  await state.reviewCandidate({id:'one',action:'confirm'})
  expect(index).not.toHaveBeenCalled()
  expect(state.reviewsError.value).toContain('unknown result')
  await state.reviewCandidate({id:'one',action:'confirm'})
  expect(index).toHaveBeenCalledOnce()
  vi.mocked(api.resolveCandidatesBatch).mockResolvedValue({items:[],processed_count:2})
  await state.reviewCandidatesBatch(['one','two'],'confirm')
  expect(api.resolveCandidatesBatch).toHaveBeenLastCalledWith(project.id,'source',['one','two'],'confirm')
  expect(state.reviewsNotice.value).toContain('2')
})

function imports() {
  const loading=reactive<IngestionLoading>({projects:false,create:false,repositories:false,remote:false,sync:false,activity:false,commit:false,sources:false,upload:false,detail:false,task:false,chunks:false,structure:false,agent:false})
  const errors=reactive<IngestionErrors>({projects:'',create:'',repositories:'',remote:'',sync:'',activity:'',commit:'',sources:'',upload:'',detail:'',task:'',chunks:'',structure:'',agent:''})
  const deps={project:ref({...project}),repositories:ref<SourceRepositoryList|null>(null),sources:ref<SourceList|null>(null),
    selectedSourceId:ref(''),selectedTaskId:ref<string|null>(null),task:ref<ProcessingTask|null>(null),notice:ref(''),loading,errors,
    locked:vi.fn(()=>false),prepareSource:vi.fn(),loadSources:vi.fn(async()=>{}),loadRepositories:vi.fn(async()=>{}),refreshSource:vi.fn(async()=>{}),errorMessage:String}
  return {...scoped(()=>useSourceImport(deps)),deps}
}
function file(name:string,path='') { const file=new File(['sample'],name);Object.defineProperty(file,'webkitRelativePath',{value:path});return file }

it('preserves partial folder success, repository paths and explicit parsing',async()=>{
  const {state,deps}=imports()
  vi.mocked(api.resolveLocalRepository).mockResolvedValue({id:'repo',name:'folder'} as api.SourceRepository)
  vi.mocked(api.uploadSource).mockRejectedValueOnce(new Error('failed file')).mockResolvedValueOnce({source_id:'ok',task_id:'task',status:'queued'})
  await state.uploadFiles([file('a.md','folder/a.md'),file('b.md','folder/nested/b.md')])
  expect(api.uploadSource).toHaveBeenLastCalledWith(project.id,expect.any(File),'nested/b.md','repo')
  expect(deps.selectedSourceId.value).toBe('ok')
  expect(deps.errors.upload).toContain('a.md')
  expect(deps.loading.upload).toBe(false)
  expect(api.runTask).not.toHaveBeenCalled()
  vi.mocked(api.runTask).mockResolvedValue({id:'task',status:'succeeded'} as ProcessingTask)
  await state.parseSource();expect(deps.task.value?.status).toBe('succeeded')
})

it('does not restore imports or continue folder writes after disposal and releases duplicate locks',async()=>{
  const {state,scope,deps}=imports()
  const pending=deferred<SourceUploadResult>()
  vi.mocked(api.uploadSource).mockReturnValueOnce(pending.promise)
  const upload=state.uploadFiles([file('a.md'),file('b.md')])
  await state.uploadFiles([file('a.md')]);expect(api.uploadSource).toHaveBeenCalledOnce()
  scope.stop();pending.resolve({source_id:'old',task_id:'old-task',status:'queued'});await upload
  expect(api.uploadSource).toHaveBeenCalledOnce()
  expect(deps.selectedSourceId.value).toBe('')
  expect(deps.loading.upload).toBe(false)
})

it('releases upload locks when refresh fails and blocks imports during another mutation',async()=>{
  const {state,deps}=imports()
  deps.locked.mockReturnValueOnce(true)
  await state.uploadFiles([file('a.md')]);expect(api.uploadSource).not.toHaveBeenCalled()
  vi.mocked(api.uploadSource).mockResolvedValue({source_id:'ok',task_id:'task',status:'queued'})
  deps.refreshSource.mockRejectedValueOnce(new Error('refresh failed'))
  await state.uploadFiles([file('a.md')])
  expect(deps.errors.upload).toContain('refresh failed')
  expect(deps.loading.upload).toBe(false)
})

it('keeps explicit remote registration/sync/activity boundaries and restores successful source selection',async()=>{
  const {state,deps}=imports()
  const repository:api.SourceRepository={id:'repo',project_id:project.id,name:'sample',kind:'git_remote',provider:'github',
    remote_owner:'example',remote_name:'sample',remote_url:'https://github.com/example/sample',provider_repository_id:null,
    created_at:project.created_at,updated_at:project.updated_at}
  vi.mocked(api.resolveGithubRepository).mockResolvedValue(repository)
  await state.registerGithubRepository({remoteUrl:repository.remote_url!})
  expect(api.syncGithubRepository).not.toHaveBeenCalled()
  const result:api.GithubRepositorySyncResult={repository_id:'repo',snapshot_id:'snapshot',ref:'main',commit_sha:'abcdef1234567',commit_url:null,
    imported_count:1,reused_count:0,unchanged_count:0,renamed_count:0,deleted_count:0,skipped_count:0,truncated:false,deletion_detection_complete:true,
    items:[{path:'note.md',previous_path:null,source_id:'imported',task_id:'task',status:'imported',error_code:null}]}
  vi.mocked(api.syncGithubRepository).mockResolvedValue(result)
  await state.syncRegisteredGithubRepository({repositoryId:'repo',ref:'main',rescan:true})
  expect(api.syncGithubRepository).toHaveBeenLastCalledWith(project.id,'repo','main',true)
  expect(deps.selectedSourceId.value).toBe('imported')
  expect(deps.refreshSource).toHaveBeenCalledOnce()
  vi.mocked(api.importGithubWorkItems).mockResolvedValue({repository_id:'repo',imported_count:0,reused_count:0,skipped_count:0,
    review_imported_count:0,review_reused_count:0,review_skipped_count:0,truncated:false,items:[]})
  await state.importRegisteredGithubActivity('repo')
  expect(api.importGithubWorkItems).toHaveBeenLastCalledWith(project.id,'repo')
  expect(deps.notice.value).toContain('Review thread 0')
  expect(deps.loading.activity).toBe(false)
})

it('discards remote results after context round trips and exposes remote failures without retry',async()=>{
  const {state,deps}=imports()
  const pending=deferred<api.SourceRepository>()
  vi.mocked(api.resolveGithubRepository).mockReturnValueOnce(pending.promise)
  const registering=state.registerGithubRepository({remoteUrl:'https://github.com/example/sample'})
  deps.project.value={...project,id:'other'};deps.project.value={...project}
  pending.resolve({id:'stale',kind:'git_remote'} as api.SourceRepository);await registering
  expect(deps.loadRepositories).not.toHaveBeenCalled()
  vi.mocked(api.syncGithubRepository).mockRejectedValueOnce(new Error('sync unavailable'))
  await state.syncRegisteredGithubRepository({repositoryId:'repo'})
  expect(deps.errors.sync).toContain('sync unavailable')
  expect(api.syncGithubRepository).toHaveBeenCalledOnce()
  expect(deps.loading.sync).toBe(false)
})

it('automatically follows pinned GitHub batches and keeps the checkpoint when a batch fails', async () => {
  const { state, deps } = imports()
  const batch: api.GithubRepositorySyncResult = {
    repository_id: 'repo', snapshot_id: 'one', ref: 'main', commit_sha: 'abcdef1234567', commit_url: null,
    imported_count: 50, reused_count: 0, unchanged_count: 0, renamed_count: 0, deleted_count: 0, skipped_count: 0,
    truncated: true, deletion_detection_complete: false, items: [],
    continuation_snapshot_id: 'one', completed_files: 50, total_supported_files: 130, remaining_files: 80, tree_complete: true,
  }
  vi.mocked(api.syncGithubRepository)
    .mockResolvedValueOnce(batch)
    .mockResolvedValueOnce({ ...batch, snapshot_id: 'two', continuation_snapshot_id: 'two', completed_files: 100, remaining_files: 30 })
    .mockRejectedValueOnce(new Error('rate limited'))
  await state.syncRegisteredGithubRepository({ repositoryId: 'repo', wholeRepository: true })
  expect(api.syncGithubRepository).toHaveBeenNthCalledWith(1, project.id, 'repo', undefined, undefined, undefined, true)
  expect(api.syncGithubRepository).toHaveBeenNthCalledWith(2, project.id, 'repo', 'main', false, 'one', true)
  expect(api.syncGithubRepository).toHaveBeenNthCalledWith(3, project.id, 'repo', 'main', false, 'two', true)
  expect(state.githubContinuations.repo?.snapshotId).toBe('two')
  expect(deps.notice.value).toContain('100 / 130')
  expect(deps.errors.sync).toContain('rate limited')

  vi.mocked(api.syncGithubRepository).mockResolvedValueOnce({ ...batch, snapshot_id: 'three', continuation_snapshot_id: null,
    completed_files: 130, remaining_files: 0, truncated: false, deletion_detection_complete: true })
  await state.syncRegisteredGithubRepository({ repositoryId: 'repo', ref: 'main', continueFromSnapshot: 'two', wholeRepository: true })
  expect(state.githubContinuations.repo).toBeUndefined()
  expect(deps.notice.value).toContain('130 / 130')
  expect(deps.notice.value).toContain('整仓导入完成')
})

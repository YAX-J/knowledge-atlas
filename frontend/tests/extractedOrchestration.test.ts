import { beforeEach, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref } from 'vue'
import * as api from '../src/api/knowledgeAtlas'
import { useEvidenceNavigation } from '../src/composables/useEvidenceNavigation'
import { useKnowledgeEvolution } from '../src/composables/useKnowledgeEvolution'
import { useRepositorySnapshots } from '../src/composables/useRepositorySnapshots'
import { errors, loading, project, source } from './fixtures'
import type { KnowledgeChange, WorkspaceNav } from '../src/types'

vi.mock('../src/api/knowledgeAtlas', () => ({ getProjectSourceChunk: vi.fn(), getEntityDetail: vi.fn(),
  getKnowledgeHistory: vi.fn(), inspectGovernance: vi.fn(), listKnowledgeChanges: vi.fn(),
  proposeKnowledgeChange: vi.fn(), resolveKnowledgeChange: vi.fn(), listRepositorySnapshots: vi.fn(),
  listSnapshotFiles: vi.fn(), importSnapshotCommit: vi.fn() }))
beforeEach(() => vi.resetAllMocks())
const describe = (error: unknown) => error instanceof Error ? error.message : 'Failed'
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes }); return { resolve, promise } }

it('locates the exact evidence page, then invalidates pending location on clear and disposal', async () => {
  const scope=effectScope(), chunks=ref<api.SourceChunkList|null>(null), focusedChunkId=ref('')
  const chunk:api.SourceChunk={ id:'chunk-45', project_id:project.id, source_id:source.id, position:44, kind:'paragraph', content:'Exact evidence',
    content_sha256:'a'.repeat(64), heading_path:[], start_line:90, end_line:90 }
  vi.mocked(api.getProjectSourceChunk).mockResolvedValue(chunk)
  const target=document.createElement('article');target.id='source-chunk-'+chunk.id;target.tabIndex=-1
  target.scrollIntoView=vi.fn();document.body.append(target)
  const refresh=vi.fn(async (page?:number)=>{ expect(page).toBe(3);chunks.value={items:[chunk],total:45,page:3,page_size:20} })
  const state=scope.run(()=>useEvidenceNavigation({project:ref(project),activeNav:ref<WorkspaceNav>('projectGraph'),
    errors:{...errors},chunks,focusedChunkId,notice:ref(''),selectedSourceId:ref(''),selectedTaskId:ref(null),
    locked:()=>false,clearSourceSelection:()=>state.clearEvidenceNavigation(),refreshSource:refresh,errorMessage:describe }))!
  await state.openEvidence({source_id:source.id,chunk_id:chunk.id})
  expect(focusedChunkId.value).toBe(chunk.id);expect(document.activeElement).toBe(target)
  const late=deferred<typeof chunk>();vi.mocked(api.getProjectSourceChunk).mockReturnValue(late.promise)
  const opening=state.openEvidence({source_id:source.id,chunk_id:chunk.id});scope.stop();late.resolve(chunk);await opening
  expect(refresh).toHaveBeenCalledTimes(1);expect(state.evidenceTarget.value).toBeNull();target.remove()
})

it('preserves failed snapshot page for retry and rejects responses after project changes', async () => {
  const scope=effectScope(), selectedProject=ref(project)
  const repository:api.SourceRepository={id:'repo',project_id:project.id,name:'Public fixture',kind:'git_remote',provider:'github',
    remote_owner:'public',remote_name:'fixture',remote_url:'https://github.com/public/fixture',provider_repository_id:'1',
    created_at:project.created_at,updated_at:project.updated_at}
  const state=scope.run(()=>useRepositorySnapshots({project:selectedProject,activeNav:ref<WorkspaceNav>('sources'),
    loading:reactive({...loading}),errors:reactive({...errors}),notice:ref(''),selectedSourceId:ref(''),selectedTaskId:ref(null),
    clearSourceSelection:vi.fn(),selectSource:vi.fn(),loadSources:vi.fn(),refreshSource:vi.fn(),errorMessage:describe }))!
  vi.mocked(api.listRepositorySnapshots).mockRejectedValueOnce(new Error('History unavailable'))
  await state.loadSnapshots(repository,2)
  expect(state.snapshotsPage.value).toBe(2);expect(state.snapshotsError.value).toBe('History unavailable')
  vi.mocked(api.listRepositorySnapshots).mockResolvedValueOnce({items:[],total:11,page:2,page_size:10})
  await state.loadSnapshots(repository,state.snapshotsPage.value)
  expect(state.snapshots.value?.page).toBe(2)
  const late=deferred<api.RepositorySnapshotFileList>();vi.mocked(api.listSnapshotFiles).mockReturnValue(late.promise)
  const opening=state.loadSnapshotFilePage('commit-1',2)
  state.clearSnapshots();selectedProject.value={...project,id:'second-project'}
  late.resolve({snapshot_id:'commit-1',repository_id:'repo',commit_sha:'a'.repeat(40),items:[],total:21,page:2,page_size:20,
    truncated:false,deletion_detection_complete:true});await opening
  expect(state.snapshotFiles.value).toBeNull();expect(state.snapshotFilesLoading.value).toBe(false);scope.stop()
})

it('fences historical writes, preserves explicit confirmation, and clears late history on navigation', async () => {
  const scope=effectScope(), busy=ref(false), context=reactive({projectId:project.id,entityId:'old',active:true,validAt:'2026-01-01'})
  const effects={clearSearch:vi.fn(),loadRealGraph:vi.fn(async()=>{}),selectEntityId:vi.fn()}
  const state=scope.run(()=>useKnowledgeEvolution(()=>context,busy,effects,describe))!
  const input={new_entity_id:'new',old_entity_id:'old',evidence_id:'evidence',kind:'SUPERSEDES' as const,
    reason:'Reviewed source',effective_at:project.created_at}
  await state.proposeChange(input);await state.resolveChange('change','confirm')
  expect(api.proposeKnowledgeChange).not.toHaveBeenCalled();expect(api.resolveKnowledgeChange).not.toHaveBeenCalled()
  context.validAt=''
  const change:KnowledgeChange={...input,id:'change',project_id:project.id,new_entity_name:'New',old_entity_name:'Old',
    review_status:'pending',resolved_at:null,created_at:project.created_at,before:{},after:{},evidence:[]}
  vi.mocked(api.proposeKnowledgeChange).mockResolvedValue(change)
  vi.mocked(api.listKnowledgeChanges).mockResolvedValue({items:[],total:0,page:1,page_size:20})
  await state.proposeChange(input)
  expect(api.proposeKnowledgeChange).toHaveBeenCalledWith(project.id,input)
  expect(api.resolveKnowledgeChange).not.toHaveBeenCalled()
  vi.mocked(api.resolveKnowledgeChange).mockResolvedValue({...change,review_status:'confirmed'})
  await state.resolveChange('change','confirm')
  expect(effects.selectEntityId).toHaveBeenCalledWith('new');expect(effects.loadRealGraph).toHaveBeenCalledWith('')
  const late=deferred<Awaited<ReturnType<typeof api.getKnowledgeHistory>>>()
  vi.mocked(api.getKnowledgeHistory).mockReturnValue(late.promise)
  const history=state.loadHistory();state.clearEvolution();context.projectId='other-project'
  late.resolve({entities:[],changes:[],truncated:false});await history
  expect(state.history.value).toBeNull();expect(busy.value).toBe(false)
  const lateWrite=deferred<KnowledgeChange>()
  vi.mocked(api.resolveKnowledgeChange).mockReturnValue(lateWrite.promise)
  const write=state.resolveChange('late-change','confirm');scope.stop();lateWrite.resolve(change);await write
  expect(state.changeNotice.value).toBe('');expect(effects.loadRealGraph).toHaveBeenCalledTimes(1)
  expect(busy.value).toBe(false)
})

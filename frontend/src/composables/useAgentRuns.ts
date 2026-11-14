import { computed, onScopeDispose, ref, watch } from 'vue'
import { ApiError } from '../api/client'
import { getAgentRun, listAgentRuns, resumeAgentRun, startAgentRun, type AgentRun, type AgentRunSummary, type WorkflowInput } from '../api/agents'
import type { Page } from '../types'

export function useAgentRuns(projectId:()=>string|undefined) {
  const runs=ref<Page<AgentRunSummary>|null>(null),selected=ref<AgentRun|null>(null)
  const loading=ref(false),sending=ref(false),unknown=ref(false),error=ref('')
  let generation=0,reads=0,disposed=false
  let pending:WorkflowInput|null=null
  const key=(project:string)=>'ka-pending-workflow:'+project
  const current=(project:string,captured:number)=>!disposed && generation===captured && projectId()===project
  const describe=(cause:unknown)=>cause instanceof Error?cause.message:'读取协作任务失败，请重试。'
  const busy=computed(()=>sending.value || unknown.value || selected.value?.status==='running')
  function store(project:string) {
    try {if(pending)sessionStorage.setItem(key(project),JSON.stringify(pending));else sessionStorage.removeItem(key(project))} catch { /* Memory remains available. */ }
  }
  async function refresh(page=runs.value?.page??1) {
    const project=projectId(),captured=generation,request=++reads
    if(!project||disposed)return
    loading.value=true;error.value=''
    try {
      const history=await listAgentRuns(project,page)
      const id=selected.value?.id??pending?.request_id
      const detail=id?await getAgentRun(project,id):null
      if(!current(project,captured)||request!==reads)return
      runs.value=history;selected.value=detail;unknown.value=false
      if(detail&&detail.status!=='running'){pending=null;store(project)}
    } catch(cause) {if(current(project,captured)&&request===reads)error.value=describe(cause)}
    finally {if(current(project,captured)&&request===reads)loading.value=false}
  }
  async function select(id:string) {
    if(sending.value||unknown.value)return
    const project=projectId(),captured=generation,request=++reads
    if(!project)return
    selected.value=null;loading.value=true;error.value=''
    try {const value=await getAgentRun(project,id);if(current(project,captured)&&request===reads){selected.value=value;if(!runs.value)void refresh()}}
    catch(cause){if(current(project,captured)&&request===reads)error.value=describe(cause)}
    finally {if(current(project,captured)&&request===reads)loading.value=false}
  }
  async function submit(input:Omit<WorkflowInput,'request_id'>,retry=false) {
    const project=projectId(),captured=generation
    if(!project||disposed||sending.value||selected.value?.status==='running'||unknown.value&&!retry)return
    if(!retry)pending={...input,request_id:crypto.randomUUID()}
    if(!pending)return
    store(project);sending.value=true;error.value=''
    try {
      const result=await startAgentRun(project,pending)
      if(!current(project,captured))return
      selected.value=result;unknown.value=false;pending=null;store(project)
      await refresh(1)
    } catch(cause) {
      if(!current(project,captured))return
      error.value=describe(cause)
      unknown.value=!(cause instanceof ApiError && cause.status>=400 && cause.status<500)
      if(!unknown.value){pending=null;store(project)}
    } finally {if(current(project,captured))sending.value=false}
  }
  async function resume() {
    const project=projectId(),id=selected.value?.id,captured=generation
    if(!project||!id||sending.value||selected.value?.status!=='awaiting_review')return
    sending.value=true;error.value=''
    try {
      const result=await resumeAgentRun(project,id)
      if(!current(project,captured))return
      selected.value=result
      if(runs.value){
        runs.value.items=runs.value.items.map(row=>row.id===id
          ? {...row,status:result.status,updated_at:result.updated_at,error_code:result.error_code}
          : row)
      }
    }
    catch(cause){if(current(project,captured))error.value=describe(cause)}
    finally {if(current(project,captured))sending.value=false}
  }
  watch(projectId,()=>{
    generation++;reads++;runs.value=selected.value=null;loading.value=sending.value=unknown.value=false;error.value='';pending=null
    const project=projectId()
    if(project){
      try {const value=JSON.parse(sessionStorage.getItem(key(project))??'null') as WorkflowInput|null
        if(value&&typeof value.request_id==='string'&&['knowledge_pipeline','question_pipeline'].includes(value.kind)){pending=value;unknown.value=true}} catch { /* Malformed storage is ignored. */ }
      void refresh(1)
    }
  },{immediate:true,flush:'sync'})
  onScopeDispose(()=>{disposed=true;generation++;reads++})
  return {runs,selected,loading,sending,unknown,error,busy,refresh,select,submit,resume,
    retry:()=>pending?submit(pending,true):Promise.resolve()}
}

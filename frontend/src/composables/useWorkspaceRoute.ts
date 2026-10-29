import { onMounted, onScopeDispose, ref, watch } from 'vue'
import type { WorkspaceNav } from '../types'

export type GraphSection = 'relations' | 'search' | 'identity' | 'evolution' | 'retirement'
export interface WorkspaceRoute {
  nav: WorkspaceNav; projectId?: string; sourceId?: string; entityId?: string
  relationshipId?: string; validAt?: string; conversationId?: string; section?: GraphSection
}
const paths: Record<WorkspaceNav,string> = {workbench:'workbench',sources:'sources',projects:'projects',
  projectGraph:'graph',graph:'demo',conversations:'conversations',questions:'questions'}
const sections:GraphSection[] = ['relations','search','identity','evolution','retirement']
const identifier=(value:string|null) => value && /^[a-zA-Z0-9-]{1,80}$/.test(value) ? value : undefined
export function parseWorkspaceRoute(hash:string,fallback:WorkspaceNav='workbench'):WorkspaceRoute {
  const [path,query='']=hash.replace(/^#\/?/,'').split('?')
  const nav=(Object.entries(paths).find(([,value])=>value===path)?.[0] as WorkspaceNav|undefined) ?? fallback
  const params=new URLSearchParams(query)
  const time=params.get('at'), section=params.get('section') as GraphSection
  return {nav,projectId:identifier(params.get('project')),sourceId:identifier(params.get('source')),
    entityId:identifier(params.get('entity')),relationshipId:identifier(params.get('relationship')),
    conversationId:identifier(params.get('conversation')),validAt:time && !Number.isNaN(Date.parse(time)) ? new Date(time).toISOString() : undefined,
    section:sections.includes(section)?section:'relations'}
}
export function encodeWorkspaceRoute(route:WorkspaceRoute) {
  const query=new URLSearchParams()
  for(const [key,value] of Object.entries({project:route.projectId,source:route.sourceId,entity:route.entityId,
    relationship:route.relationshipId,at:route.validAt,conversation:route.conversationId,
    section:route.nav==='projectGraph' && route.section!=='relations'?route.section:undefined})) {
    if(value)query.set(key,value)
  }
  return '#/'+paths[route.nav]+(query.size?'?'+query:'')
}

export function useWorkspaceRoute(state:()=>WorkspaceRoute, restore:(route:WorkspaceRoute,current:()=>boolean)=>Promise<void>,locked:()=>boolean) {
  const error=ref('');let ready=false,restoring=false,disposed=false,generation=0
  function write(push=false) {
    const hash=encodeWorkspaceRoute(state())
    if(window.location.hash!==hash)window.history[push?'pushState':'replaceState'](null,'',hash)
  }
  async function read() {
    if(locked()){write();return}
    const captured=++generation;restoring=true;error.value=''
    try { await restore(parseWorkspaceRoute(window.location.hash,state().nav),()=>!disposed && captured===generation) }
    catch(value){if(captured===generation)error.value=value instanceof Error?value.message:'无法恢复此位置，请重试。'}
    finally {if(!disposed && captured===generation){restoring=false;ready=true;if(!error.value)write()}}
  }
  watch(()=>encodeWorkspaceRoute(state()),(_value,previous)=>{
    if(ready && !restoring){
      const prior=parseWorkspaceRoute(previous??'',state().nav),next=state()
      write(prior.nav!==next.nav || prior.projectId!==next.projectId || prior.section!==next.section)
    }
  },{flush:'post'})
  onMounted(()=>{window.addEventListener('popstate',read);window.addEventListener('hashchange',read);void read()})
  onScopeDispose(()=>{disposed=true;generation++;window.removeEventListener('popstate',read);window.removeEventListener('hashchange',read)})
  function cancelRouteRestore() { generation++;restoring=false;ready=true;error.value='' }
  return {routeError:error,retryRoute:read,cancelRouteRestore}
}

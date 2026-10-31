import { computed, onScopeDispose, ref, watch } from 'vue'
import { ApiError } from '../api/client'
import { createNote, editNote, getNote, getNoteHistory, getNoteRevision, listNotes, type Note, type NoteEdit, type NoteRevision, type NoteSummary } from '../api/notes'
interface SavedNotes {noteId?:string;title?:string;markdown?:string;base?:string;dirty?:boolean;pending?:{noteId:string;input:NoteEdit}|null;pendingCreate?:{request_id:string;title:string;markdown:string}|null}

export function useNotes(projectId:()=>string|undefined) {
  const items=ref<NoteSummary[]>([]), selected=ref<Note|null>(null), historical=ref<NoteRevision|null>(null), revisions=ref<NoteRevision[]>([])
  const title=ref(''), markdown=ref(''), loading=ref(false), saving=ref(false), unknown=ref(false), conflict=ref(false), error=ref(''), query=ref(''), page=ref(1), total=ref(0), truncated=ref(false)
  let generation=0,reads=0,listReads=0,disposed=false,timer:ReturnType<typeof setTimeout>|undefined
  let pending:{noteId:string;input:NoteEdit}|null=null, pendingCreate:{request_id:string;title:string;markdown:string}|null=null
  const key=(id:string)=>`ka-notes:${id}`
  const current=(id:string,v:number)=>!disposed&&projectId()===id&&v===generation
  const dirty=computed(()=>!!selected.value&&!historical.value&&(title.value!==selected.value.current.title||markdown.value!==selected.value.current.markdown))
  const blocked=computed(()=>saving.value||unknown.value||conflict.value||dirty.value)
  function cache() {const id=projectId();if(!id||!selected.value&&!pendingCreate)return;try{sessionStorage.setItem(key(id),JSON.stringify({noteId:selected.value?.id,title:title.value,markdown:markdown.value,base:selected.value?.current.id,dirty:dirty.value,pending,pendingCreate}))}catch{/* Preserve in memory. */}}
  const message=(cause:unknown)=>cause instanceof Error?cause.message:'笔记请求失败，请重试。'
  async function refresh() {
    const id=projectId(),v=generation,read=++listReads;if(!id)return
    loading.value=true
    try {const rows=await listNotes(id,page.value,query.value);if(!current(id,v)||read!==listReads)return;items.value=rows.items;total.value=rows.total;truncated.value=rows.truncated}
    catch(cause){if(current(id,v)&&read===listReads)error.value=message(cause)}finally{if(current(id,v)&&read===listReads)loading.value=false}
  }
  async function select(id:string,discard=false) {
    const project=projectId(),v=generation,read=++reads;if(!project||saving.value||blocked.value&&!discard)return
    clearTimeout(timer);loading.value=true
    try {
      const note=await getNote(project,id),history=await getNoteHistory(project,id)
      if(!current(project,v)||read!==reads)return
      selected.value=note;historical.value=null;revisions.value=history;title.value=note.current.title;markdown.value=note.current.markdown
      pending=null;unknown.value=false;conflict.value=false;error.value='';cache()
    }catch(cause){if(current(project,v)&&read===reads)error.value=message(cause)}finally{if(current(project,v)&&read===reads)loading.value=false}
  }
  async function openRevision(id:string) {
    const project=projectId(),v=generation,read=++reads;if(!project)return
    if(blocked.value){error.value='请先保存或处理当前草稿，再重新打开引用。';return}
    try{const revision=await getNoteRevision(project,id),note=await getNote(project,revision.note_id),history=await getNoteHistory(project,revision.note_id)
      if(current(project,v)&&read===reads){selected.value=note;title.value=note.current.title;markdown.value=note.current.markdown;revisions.value=history;historical.value=revision;cache()}}
    catch(cause){if(current(project,v))error.value=message(cause)}
  }
  async function save(retry=false) {
    const project=projectId(),note=selected.value,v=generation
    if(!project||!note||saving.value||historical.value||conflict.value||!title.value.trim()||unknown.value&&!retry)return
    if(!retry&&!dirty.value)return
    if(!pending)pending={noteId:note.id,input:{request_id:crypto.randomUUID(),expected_revision_id:note.current.id,title:title.value.trim(),markdown:markdown.value}}
    const attempt=pending;saving.value=true;error.value='';cache()
    try {
      const revision=await editNote(project,attempt.noteId,attempt.input)
      if(!current(project,v))return
      selected.value={...note,current:revision};revisions.value=[revision,...revisions.value.filter(r=>r.id!==revision.id)]
      if(title.value===attempt.input.title&&markdown.value===attempt.input.markdown){title.value=revision.title;markdown.value=revision.markdown}
      pending=null;unknown.value=false;cache();await refresh()
    }catch(cause){if(!current(project,v))return;error.value=message(cause);conflict.value=cause instanceof ApiError&&cause.status===409;unknown.value=!(cause instanceof ApiError&&cause.status>=400&&cause.status<500);if(!unknown.value)pending=null;cache()}
    finally {if(current(project,v)){saving.value=false;if(dirty.value&&!unknown.value&&!conflict.value)schedule()}}
  }
  async function resolveUnknown() {
    const project=projectId(),v=generation,attempt=pending;if(!project||saving.value)return
    if(pendingCreate){try{const note=await getNote(project,pendingCreate.request_id);if(!current(project,v))return;selected.value=note;title.value=note.current.title;markdown.value=note.current.markdown;historical.value=null;pendingCreate=null;unknown.value=false;cache();await refresh()}catch(cause){if(current(project,v))error.value=message(cause)}return}
    if(!attempt)return
    try {const revision=await getNoteRevision(project,attempt.input.request_id);if(!current(project,v))return
      if(revision.note_id!==attempt.noteId)return
      const latest=await getNote(project,attempt.noteId);if(!current(project,v))return
      selected.value=latest;pending=null;unknown.value=false;conflict.value=latest.current.id!==revision.id;cache();if(dirty.value&&!conflict.value)schedule()
    }catch(cause){if(current(project,v))error.value=message(cause)}
  }
  async function create(retry=false) {
    const project=projectId(),v=generation;if(!project||saving.value||dirty.value||conflict.value||unknown.value&&!retry)return
    if(!pendingCreate)pendingCreate={request_id:crypto.randomUUID(),title:'新笔记',markdown:''}
    saving.value=true;cache()
    try {const note=await createNote(project,pendingCreate);if(!current(project,v))return;pendingCreate=null;unknown.value=false;selected.value=note;title.value=note.current.title;markdown.value=note.current.markdown;historical.value=null;revisions.value=[note.current];cache();await refresh()}
    catch(cause){if(current(project,v)){error.value=message(cause);unknown.value=!(cause instanceof ApiError&&cause.status>=400&&cause.status<500);if(!unknown.value)pendingCreate=null;cache()}}
    finally{if(current(project,v))saving.value=false}
  }
  function schedule(){clearTimeout(timer);if(dirty.value&&!saving.value&&!unknown.value&&!conflict.value)timer=setTimeout(()=>void save(),600)}
  watch([title,markdown],()=>{cache();schedule()})
  watch(projectId,async()=>{
    generation++;reads++;listReads++;clearTimeout(timer);pending=null;pendingCreate=null;selected.value=null;historical.value=null;revisions.value=[];items.value=[];title.value='';markdown.value='';error.value='';unknown.value=conflict.value=saving.value=loading.value=false;page.value=1;query.value=''
    const project=projectId(),v=generation;if(!project)return
    // Read saved state before the draft watchers can replace it.
    let cached:SavedNotes|null=null
    try{cached=JSON.parse(sessionStorage.getItem(key(project))??'null') as SavedNotes|null}catch{/* Ignore malformed cache. */}
    await refresh();if(!current(project,v))return
    if(cached?.pendingCreate){pendingCreate=cached.pendingCreate;unknown.value=true;return}
    if(cached?.noteId){
      await select(cached.noteId);if(!current(project,v))return
      if((cached.dirty!==false||cached.pending)&&typeof cached.title==='string'&&typeof cached.markdown==='string'){
        title.value=cached.title;markdown.value=cached.markdown;pending=cached.pending??null;unknown.value=!!pending
        conflict.value=!!cached.base&&cached.base!==(selected.value as Note|null)?.current.id&&dirty.value
        // Refresh only reads. A recovered unsaved draft requires explicit save.
        if(dirty.value&&!unknown.value)conflict.value=true
        cache()
      }
    }
  },{immediate:true,flush:'sync'})
  onScopeDispose(()=>{cache();disposed=true;generation++;reads++;clearTimeout(timer)})
  return {items,selected,historical,revisions,title,markdown,loading,saving,unknown,conflict,error,query,page,total,truncated,dirty,blocked,refresh,select,openRevision,save,resolveUnknown,create,
    retry:()=>pending?save(true):create(true),reload:()=>selected.value?select(selected.value.id,true):Promise.resolve()}
}

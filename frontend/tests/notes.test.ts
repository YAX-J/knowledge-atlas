import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import * as api from '../src/api/notes'
import { ApiError } from '../src/api/client'
import { useNotes } from '../src/composables/useNotes'
import NotesPanel from '../src/components/agent/NotesPanel.vue'
import { project } from './fixtures'
vi.mock('../src/api/notes')
enableAutoUnmount(afterEach)
const revision:api.NoteRevision={id:'rev-1',note_id:'note-1',project_id:project.id,number:1,parent_revision_id:null,title:'First note',markdown:'<script>raw</script>\nPostgreSQL',content_sha256:'a'.repeat(64),origin:'human',task_id:null,provenance:{},created_at:project.created_at}
const note:api.Note={id:'note-1',project_id:project.id,current:revision,updated_at:project.updated_at}
beforeEach(()=>{vi.resetAllMocks();sessionStorage.clear();vi.mocked(api.listNotes).mockResolvedValue({items:[{id:note.id,current_revision_id:revision.id,title:revision.title,preview:'text',content_sha256:revision.content_sha256,origin:'human'}],total:1,page:1,page_size:20,truncated:false});vi.mocked(api.getNote).mockResolvedValue(note);vi.mocked(api.getNoteHistory).mockResolvedValue([revision]);vi.mocked(api.getNoteRevision).mockResolvedValue(revision)})
afterEach(()=>vi.useRealTimers())
function harness(){let state!:ReturnType<typeof useNotes>;const id=ref<string|undefined>(project.id);const wrapper=mount(defineComponent({setup(){state=useNotes(()=>id.value);return()=>null}}));return {wrapper,get state(){return state},id}}

it('autosaves a new immutable revision after debounce and attaches exact revision IDs',async()=>{
  vi.mocked(api.editNote).mockResolvedValue({...revision,id:'rev-2',number:2,parent_revision_id:revision.id,markdown:'Changed'})
  const wrapper=mount(NotesPanel,{props:{projectId:project.id}});await flushPromises()
  await wrapper.findAll('button').find(b=>b.text().includes('First note'))!.trigger('click');await flushPromises()
  vi.useFakeTimers();await wrapper.get('textarea').setValue('Changed');expect(api.editNote).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(650);await flushPromises()
  expect(api.editNote).toHaveBeenCalledWith(project.id,note.id,expect.objectContaining({expected_revision_id:revision.id,markdown:'Changed'}))
  expect(wrapper.text()).toContain('修订 2')
  await wrapper.findAll('button').find(b=>b.text()==='将此修订附加到助手')!.trigger('click')
  expect(wrapper.emitted('attach')).toEqual([['rev-2']])
})

it('renders historical content safely without making an edit request',async()=>{
  const wrapper=mount(NotesPanel,{props:{projectId:project.id}});await flushPromises();await wrapper.setProps({revisionId:revision.id});await flushPromises()
  expect(wrapper.text()).toContain('<script>raw</script>');expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('历史修订 1');expect(api.editNote).not.toHaveBeenCalled()
})

it('opens the matching note during simultaneous list refresh and artifact navigation',async()=>{
  const draft={...revision,id:'draft-rev',note_id:'draft-note',title:'Agent report'}
  vi.mocked(api.getNoteRevision).mockResolvedValue(draft);vi.mocked(api.getNote).mockResolvedValue({...note,id:draft.note_id,current:draft})
  const wrapper=mount(NotesPanel,{props:{projectId:project.id}});await flushPromises()
  await wrapper.setProps({revisionId:draft.id,refreshToken:1});await flushPromises()
  expect(wrapper.text()).toContain('历史修订 1 · Agent report')
  await wrapper.findAll('button').find(b=>b.text()==='返回编辑器')!.trigger('click')
  expect((wrapper.get('input[maxlength="120"]').element as HTMLInputElement).value).toBe('Agent report')
})

it('preserves a conflict draft and pauses automatic writes',async()=>{
  vi.mocked(api.editNote).mockRejectedValue(new ApiError(409,{error:{code:'NOTE_REVISION_CONFLICT',message:'new revision'}}))
  const h=harness();await flushPromises();await h.state.select(note.id);h.state.markdown.value='Local unsaved';await h.state.save()
  expect(h.state.conflict.value).toBe(true);expect(h.state.markdown.value).toBe('Local unsaved')
  await h.state.save();expect(api.editNote).toHaveBeenCalledOnce()
  expect(sessionStorage.getItem(`ka-notes:${project.id}`)).toContain('Local unsaved')
})

it('restores an unknown save with GET and never repeats PUT automatically',async()=>{
  vi.mocked(api.editNote).mockRejectedValue(new ApiError(0,{error:{message:'Unknown outcome'}}))
  const h=harness();await flushPromises();await h.state.select(note.id);h.state.markdown.value='New text';await h.state.save()
  const input=vi.mocked(api.editNote).mock.calls[0]![2]
  expect(h.state.unknown.value).toBe(true);h.wrapper.unmount()
  vi.mocked(api.getNoteRevision).mockResolvedValue({...revision,id:input.request_id,markdown:input.markdown})
  vi.mocked(api.getNote).mockResolvedValue({...note,current:{...revision,id:input.request_id,markdown:input.markdown}})
  const restored=harness();await flushPromises();expect(api.editNote).toHaveBeenCalledOnce()
  await restored.state.resolveUnknown();expect(api.getNoteRevision).toHaveBeenCalledWith(project.id,input.request_id)
  expect(restored.state.unknown.value).toBe(false);expect(api.editNote).toHaveBeenCalledOnce()
})

it('keeps edits made during an in-flight save for the next revision',async()=>{
  let resolve!:(r:api.NoteRevision)=>void
  vi.mocked(api.editNote).mockReturnValue(new Promise(r=>{resolve=r}))
  const h=harness();await flushPromises();await h.state.select(note.id);h.state.markdown.value='first';const pending=h.state.save();h.state.markdown.value='second'
  resolve({...revision,id:'rev-2',number:2,markdown:'first'});await pending
  expect(h.state.markdown.value).toBe('second');expect(h.state.selected.value?.current.id).toBe('rev-2');expect(h.state.dirty.value).toBe(true)
})

it('fences stale project responses and leaves the prior draft in its project cache',async()=>{
  const h=harness();await flushPromises();await h.state.select(note.id);h.state.markdown.value='Private to project one';await flushPromises()
  let resolve!:(r:api.NoteRevision)=>void;vi.mocked(api.editNote).mockReturnValue(new Promise(r=>{resolve=r}))
  const save=h.state.save();h.id.value='project-other';resolve({...revision,id:'old-response'});await save;await flushPromises()
  expect(h.state.selected.value).toBeNull();expect(h.state.markdown.value).toBe('')
  expect(sessionStorage.getItem(`ka-notes:${project.id}`)).toContain('Private to project one')
})

it('creates notes only on explicit intent and recovers creation UUIDs for explicit replay',async()=>{
  vi.mocked(api.createNote).mockRejectedValueOnce(new ApiError(0,{error:{message:'Unknown'}})).mockResolvedValue(note)
  const h=harness();await flushPromises();expect(api.createNote).not.toHaveBeenCalled();await h.state.create()
  const input=vi.mocked(api.createNote).mock.calls[0]![1];expect(h.state.unknown.value).toBe(true)
  await h.state.retry();expect(vi.mocked(api.createNote).mock.calls[1]![1]).toEqual(input)
  expect(h.state.selected.value?.id).toBe(note.id)
})

it('resolves an unknown creation by GET without another POST',async()=>{
  vi.mocked(api.createNote).mockRejectedValueOnce(new ApiError(0,{error:{message:'Unknown'}}))
  const h=harness();await flushPromises();await h.state.create();const id=vi.mocked(api.createNote).mock.calls[0]![1].request_id
  vi.mocked(api.getNote).mockResolvedValue({...note,id});await h.state.resolveUnknown()
  expect(api.getNote).toHaveBeenCalledWith(project.id,id);expect(h.state.unknown.value).toBe(false);expect(api.createNote).toHaveBeenCalledOnce()
})

it('reloads the latest approved revision when the cached editor was clean',async()=>{
  sessionStorage.setItem(`ka-notes:${project.id}`,JSON.stringify({noteId:note.id,title:'Old saved title',markdown:'Old saved content',base:'old-rev',dirty:false}))
  const h=harness();await flushPromises();expect(h.state.markdown.value).toBe(revision.markdown);expect(h.state.conflict.value).toBe(false);expect(api.editNote).not.toHaveBeenCalled()
})

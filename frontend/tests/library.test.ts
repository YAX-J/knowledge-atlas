import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import ProjectManagement from '../src/components/ProjectManagement.vue'
import SourceArchiveControl from '../src/components/SourceArchiveControl.vue'
import AnswerFeedbackPanel from '../src/components/AnswerFeedbackPanel.vue'
import * as api from '../src/api/library'
import { project } from './fixtures'
import type { QuestionAnswer } from '../src/types'

vi.mock('../src/api/library',()=>({editProject:vi.fn(),archiveProject:vi.fn(),archivedProjects:vi.fn(),archiveSource:vi.fn(),listFeedback:vi.fn(),saveFeedback:vi.fn()}))
enableAutoUnmount(afterEach)
beforeEach(()=>{vi.resetAllMocks();vi.mocked(api.listFeedback).mockResolvedValue([])})
const answer={id:'answer',claims:[{text:'A saved claim',status:'supported',citation_ids:['evidence']}]} as QuestionAnswer

it('edits a project with its revision and performs only explicit archive/restore actions',async()=>{
 const wrapper=mount(ProjectManagement,{props:{project,locked:false}})
 vi.mocked(api.editProject).mockResolvedValue({...project,name:'Updated'})
 await wrapper.get('input').setValue('Updated');await wrapper.get('form').trigger('submit');await flushPromises()
 expect(api.editProject).toHaveBeenCalledWith(project,'Updated',project.description)
 expect(wrapper.emitted('updated')?.[0]?.[0]).toMatchObject({name:'Updated'})
 vi.mocked(api.archiveProject).mockResolvedValue({...project,archived_at:'2026-11-26T00:00:00Z'})
 await wrapper.findAll('button').find(button=>button.text()==='归档当前项目')!.trigger('click');await flushPromises()
 expect(api.archiveProject).toHaveBeenCalledWith(project,true)
 expect(api.archivedProjects).not.toHaveBeenCalled()
})

it('archives sources explicitly, releases busy state on errors, and avoids writes after unmount',async()=>{
 const wrapper=mount(SourceArchiveControl,{props:{projectId:project.id,sourceId:'source',archived:false,locked:false}})
 await wrapper.get('form').trigger('submit');expect(api.archiveSource).not.toHaveBeenCalled()
 await wrapper.get('input').setValue('Old import')
 vi.mocked(api.archiveSource).mockRejectedValueOnce(new Error('Unknown response'))
 await wrapper.get('form').trigger('submit');await flushPromises()
 expect(wrapper.get('[role=alert]').text()).toContain('Unknown response')
 expect(wrapper.emitted('changed')).toBeUndefined()
 expect(wrapper.emitted('busy')?.at(-1)).toEqual([false])
 vi.mocked(api.archiveSource).mockResolvedValue({source_id:'source',archived:true})
 await wrapper.get('form').trigger('submit');await flushPromises()
 expect(api.archiveSource).toHaveBeenLastCalledWith(project.id,'source',true,'Old import')
 expect(wrapper.emitted('changed')).toHaveLength(1)
})

it('retains the same feedback request after an unknown response and refreshes with GET only',async()=>{
 const wrapper=mount(AnswerFeedbackPanel,{props:{projectId:project.id,turnId:'turn',answer}})
 await flushPromises();await wrapper.get('textarea').setValue('The citation is unrelated.')
 vi.mocked(api.saveFeedback).mockRejectedValueOnce(new Error('Unknown response'))
 await wrapper.get('form').trigger('submit');await flushPromises()
 const input=vi.mocked(api.saveFeedback).mock.calls[0]![2]
 expect(input.claim_index).toBe(0);expect(input.comment).toBe('The citation is unrelated.')
 await wrapper.findAll('button').find(button=>button.text()==='刷新纠错记录')!.trigger('click');await flushPromises()
 expect(api.saveFeedback).toHaveBeenCalledTimes(1)
 vi.mocked(api.saveFeedback).mockResolvedValue({id:input.request_id,turn_id:'turn',answer_sha256:'a'.repeat(64),claim_index:0,claim_text:'A saved claim',category:'incorrect',comment:input.comment,created_at:'2026-11-26T00:00:00Z'})
 await wrapper.get('form').trigger('submit');await flushPromises()
 expect(vi.mocked(api.saveFeedback).mock.calls[1]![2]).toEqual(input)
 expect(wrapper.get('[role=status]').text()).toContain('原答案和知识未改写')
})

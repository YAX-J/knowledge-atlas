import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { effectScope, ref } from 'vue'
import CandidateReview from '../src/components/CandidateReview.vue'
import { useCandidateReview } from '../src/composables/useCandidateReview'
import * as batches from '../src/api/extraction'
import * as api from '../src/api/knowledgeAtlas'
import { project } from './fixtures'

vi.mock('../src/api/extraction',()=>({getExtractionPlan:vi.fn(),extractBatches:vi.fn()}))
vi.mock('../src/api/knowledgeAtlas',()=>({extractKnowledge:vi.fn(),getExtraction:vi.fn(),listCandidates:vi.fn(),resolveCandidate:vi.fn(),resolveCandidatesBatch:vi.fn()}))
enableAutoUnmount(afterEach)
beforeEach(()=>vi.resetAllMocks())
const plan={protocol:'extraction-batches-v1',plan_sha256:'a'.repeat(64),batch_count:2,max_batches:8,chunk_count:120,fragment_count:120,input_chars:[3000,1000],input_limit:60000,model:'local-stub',cached:false}

it('previews for free and requires a separate explicit plan-bound extraction action',async()=>{
 const wrapper=mount(CandidateReview,{props:{candidates:null,extraction:null,loading:false,extracting:false,resolving:'',error:'',notice:''}})
 await wrapper.findAll('button').find(button=>button.text()==='免费预览分批计划')!.trigger('click')
 expect(wrapper.emitted('previewBatches')).toHaveLength(1)
 expect(wrapper.emitted('extract')).toBeUndefined()
 await wrapper.setProps({batchPlan:plan})
 expect(wrapper.text()).toContain('最多 2 次模型请求')
 await wrapper.findAll('button').find(button=>button.text()==='确认按 2 批提取候选')!.trigger('click')
 expect(wrapper.emitted('extract')).toEqual([[plan.plan_sha256]])
})

it('keeps plan reads separate from paid actions and clears stale plans on source changes',async()=>{
 const scope=effectScope(),source=ref('source')
 const state=scope.run(()=>useCandidateReview(ref(project),source,vi.fn(),value=>String(value)))!
 vi.mocked(batches.getExtractionPlan).mockResolvedValue(plan)
 await state.previewBatches()
 expect(state.batchPlan.value).toEqual(plan)
 expect(batches.extractBatches).not.toHaveBeenCalled();expect(api.extractKnowledge).not.toHaveBeenCalled()
 vi.mocked(batches.extractBatches).mockRejectedValue(new Error('Plan changed'))
 await state.extractSource(plan.plan_sha256)
 expect(batches.extractBatches).toHaveBeenCalledExactlyOnceWith('source',plan.plan_sha256)
 expect(state.reviewsError.value).toContain('Plan changed')
 source.value='different'
 expect(state.batchPlan.value).toBeNull()
 scope.stop()
})

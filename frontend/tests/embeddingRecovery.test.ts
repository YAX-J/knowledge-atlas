import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import KnowledgeSearch from '../src/components/KnowledgeSearch.vue'

enableAutoUnmount(afterEach)
it('shows persisted partial batches and requires explicit interrupted rebuild',async()=>{
 const wrapper=mount(KnowledgeSearch,{props:{result:null,loading:false,error:'',errorAction:'search',labels:{},rebuilding:false,notice:'',
  embeddingJob:{id:'job',project_id:'project',status:'running',interrupted:true,started_at:'2026-11-26T00:00:00Z',lease_expires_at:'2026-11-26T00:01:00Z',completed_at:null,error:null,
   result:{model:'model',dimensions:1024,eligible_count:64,updated_count:32,reused_count:0,remaining_count:32,completed_batches:1}}}})
 expect(wrapper.text()).toContain('已保存 32 条，本轮剩余 32 条')
 expect(wrapper.text()).toContain('覆盖可能不完整')
 expect(wrapper.emitted('rebuild')).toBeUndefined()
 await wrapper.findAll('button').find(button=>button.text()==='明确重新更新索引')!.trigger('click')
 expect(wrapper.emitted('rebuild')).toEqual([[true]])
})

import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import ProjectGraph from '../src/components/ProjectGraph.vue'
import { project } from './fixtures'
import type { FormalKnowledgeNode } from '../src/types'

enableAutoUnmount(afterEach)
const node:FormalKnowledgeNode={id:'node',project_id:project.id,candidate_id:'candidate',type:'Concept',name:'Evidence anchor',summary:'Source-backed',confidence:.9,status:'active',valid_from:project.created_at,valid_to:null,evidence_count:1}
const props={project,graph:{nodes:[node],edges:[],truncated:false},entityDetail:{entity:node,evidence:[],relationships:[],truncated:false},relationshipDetail:null,
 loading:false,detailLoading:false,error:'',detailError:'',selectedId:node.id,center:'',depth:1,typeFilter:'',searchResult:null,searchLoading:false,
 searchError:'',searchErrorAction:'search' as const,searchRebuilding:false,searchNotice:'',validAt:'',mutationBusy:false,section:'relations' as const}
it('keeps graph keyboard selection and search in distinct task sections',async()=>{
 const wrapper=mount(ProjectGraph,{props,attachTo:document.body})
 await wrapper.get('[aria-label="查看知识：Evidence anchor"]').trigger('keydown.enter')
 expect(wrapper.emitted('selectEntity')?.[0]).toEqual([node.id])
 await wrapper.get('[aria-label="知识工作区"]').findAll('button')[1]!.trigger('click')
 expect(wrapper.emitted('section')?.[0]).toEqual(['search'])
 await wrapper.setProps({section:'search'})
 expect(wrapper.get('.real-graph-layout').isVisible()).toBe(false)
 expect(wrapper.get('.knowledge-search').isVisible()).toBe(true)
})
it('preserves history controls and blocks task switching during mutation',async()=>{
 const wrapper=mount(ProjectGraph,{props:{...props,section:'identity'},attachTo:document.body})
 expect(wrapper.get('.context-node-picker').text()).toContain('Evidence anchor')
 await wrapper.get('input[type=datetime-local]').setValue('2023-03-20T00:00')
 await wrapper.get('.time-query').trigger('submit')
 expect(wrapper.emitted('time')?.[0]?.[0]).toMatch(/^2023-03/)
 await wrapper.setProps({mutationBusy:true})
 expect(wrapper.get('[aria-label="知识工作区"]').findAll('button').every(item=>item.attributes('disabled')!==undefined)).toBe(true)
})

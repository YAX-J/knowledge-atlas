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

it('filters and highlights association paths locally, supports keyboard layout, and clears context on project changes',async()=>{
 const second={...node,id:'second',name:'Database'},third={...node,id:'third',name:'Service'}
 const firstEdge={...node,id:'edge-a',type:'USES',name:'Uses database',source_id:node.id,target_id:second.id}
 const secondEdge={...node,id:'edge-b',type:'DEPENDS_ON',name:'Depends on service',source_id:second.id,target_id:third.id}
 const wrapper=mount(ProjectGraph,{props:{...props,graph:{nodes:[node,second,third],edges:[firstEdge,secondEdge],truncated:true}}})
 const controls=wrapper.get('[aria-label="图谱布局与关联路径"]')
 const selects=controls.findAll('select')
 await selects[0]!.setValue('directed')
 await selects[2]!.setValue(node.id);await selects[3]!.setValue(third.id)
 expect(wrapper.findAll('.real-edge.path-highlight')).toHaveLength(2)
 expect(wrapper.text()).toContain('当前子图中找到 2 跳关联路径')
 const target=wrapper.get('.real-node'),before=target.attributes('transform')
 await target.trigger('keydown',{key:'ArrowRight',altKey:true})
 expect(target.attributes('transform')).not.toBe(before)
 await controls.get('button').trigger('click')
 expect(target.attributes('transform')).toBe(before)
 await selects[1]!.setValue('USES')
 expect(wrapper.findAll('.real-edge')).toHaveLength(1)
 expect(wrapper.text()).toContain('当前子图与关系筛选下未找到关联路径')
 expect(wrapper.emitted('selectEntity')).toBeUndefined()
 expect(wrapper.emitted('refresh')).toBeUndefined()
 await wrapper.setProps({project:{...project,id:'another'}})
 expect((selects[1]!.element as HTMLSelectElement).value).toBe('')
 expect((selects[2]!.element as HTMLSelectElement).value).toBe('')
})
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
it('gives the canvas the full layout until filters or details are opened', async () => {
  const wrapper = mount(ProjectGraph, { props, attachTo: document.body })
  const filters = wrapper.get('#graph-controls')
  const details = wrapper.get('#formal-knowledge-detail')
  const filterButton = wrapper.get('[aria-controls="graph-controls"]')
  expect(filters.isVisible()).toBe(false)
  expect(details.isVisible()).toBe(false)
  await filterButton.trigger('click')
  expect(filters.isVisible()).toBe(true)
  await wrapper.get('[aria-label="收起筛选"]').trigger('click')
  expect(filters.isVisible()).toBe(false)
  expect(document.activeElement).toBe(filterButton.element)
  await wrapper.get('.real-node').trigger('click')
  expect(details.isVisible()).toBe(true)
  expect(wrapper.emitted('selectEntity')).toEqual([[node.id]])
  await wrapper.get('[aria-label="放大画布"]').trigger('click')
  expect(wrapper.get('[aria-label="画布缩放比例"]').text()).toBe('125%')
  await wrapper.get('[aria-label="适应画布"]').trigger('click')
  expect(wrapper.get('[aria-label="画布缩放比例"]').text()).toBe('100%')
  await wrapper.setProps({ wideCanvas: true })
  expect(details.isVisible()).toBe(false)
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

it('switches data sources, shows whole-snapshot totals, and exposes the explicit sync action', async () => {
 const wrapper = mount(ProjectGraph, { props })
 await wrapper.get('.graph-source-bar select').setValue('neo4j')
 expect(wrapper.emitted('backend')?.[0]).toEqual(['neo4j'])
 await wrapper.setProps({ backend: 'neo4j', neo4jSnapshot: { valid_at: project.created_at, node_count: 7, edge_count: 4 } })
 expect(wrapper.find('input[type=datetime-local]').exists()).toBe(false)
 expect(wrapper.get('.graph-snapshot time').attributes('datetime')).toBe(project.created_at)
 expect(wrapper.get('.graph-snapshot').text()).toContain('共 7 个节点、4 条关系')
 expect(wrapper.get('.graph-count').text()).toContain('显示 1 个节点、0 条关系')
 await wrapper.get('.graph-source-bar button').trigger('click')
 expect(wrapper.emitted('syncNeo4j')).toHaveLength(1)
 await wrapper.setProps({ neo4jSyncing: true })
 expect(wrapper.get('.graph-source-bar button').attributes('disabled')).toBeDefined()
 await wrapper.setProps({ neo4jSyncing: false, neo4jSyncError: '同步失败' })
 expect(wrapper.get('[role=alert]').text()).toBe('同步失败')
})

it('previews and commits historical graph stops, including sub-millisecond boundaries', async () => {
  const older = '2026-04-01T00:00:00Z'
  const newer = '2026-04-01T00:00:00.000005Z'
  const edge = { ...node, id: 'old', name: 'Old database', source_id: node.id, target_id: node.id,
    status: 'superseded', valid_from: older, valid_to: newer }
  const wrapper = mount(ProjectGraph, { props: { ...props,
    graph: { ...props.graph, edges: [edge] }, timeline: { instants: [older, newer], truncated: false },
  } })
  const slider = wrapper.get<HTMLInputElement>('#graph-time-slider')
  expect(slider.element.value).toBe('2')
  slider.element.value = '0'
  await slider.trigger('input')
  expect(wrapper.emitted('time')).toBeUndefined()
  await slider.trigger('change')
  expect(wrapper.emitted('time')).toEqual([[older]])
  await wrapper.setProps({ validAt: older })
  expect(wrapper.get('.real-edge.ended').attributes('aria-label')).toContain('后来失效')
  await slider.setValue('1')
  expect(wrapper.emitted('time')?.[1]).toEqual([newer])
  await wrapper.setProps({ validAt: newer })
  expect(slider.attributes('aria-valuetext')).toContain('.000005')
  await slider.setValue('2')
  expect(wrapper.emitted('time')?.[2]).toEqual([''])
  await wrapper.setProps({ backend: 'neo4j' })
  expect(wrapper.find('#graph-time-slider').exists()).toBe(false)
})

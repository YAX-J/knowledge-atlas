import { afterEach, expect, it, vi } from 'vitest'
import { defineComponent, h, reactive } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { encodeWorkspaceRoute, parseWorkspaceRoute, useWorkspaceRoute, type WorkspaceRoute } from '../src/composables/useWorkspaceRoute'

enableAutoUnmount(afterEach)
afterEach(()=>window.history.replaceState(null,'','#'))
it('round trips project/source/history context and rejects invalid route inputs',()=>{
  const route:WorkspaceRoute={nav:'projectGraph',projectId:'project-1',sourceId:'source-1',entityId:'entity-1',validAt:'2023-03-20T00:00:00.000Z',section:'identity'}
  expect(parseWorkspaceRoute(encodeWorkspaceRoute(route))).toMatchObject(route)
  const invalid=parseWorkspaceRoute('#/unknown?project=../../secrets&at=nonsense&section=unsafe')
  expect(invalid.nav).toBe('workbench');expect(invalid.projectId).toBeUndefined();expect(invalid.validAt).toBeUndefined()
  expect(invalid.section).toBe('relations')
})
it('restores initial and browser-back locations while refusing navigation under a write lock',async()=>{
  window.history.replaceState(null,'','#/sources?project=project-1&source=source-1')
  const state=reactive<WorkspaceRoute>({nav:'workbench'});let locked=false
  const restore=vi.fn(async(route:WorkspaceRoute)=>{Object.assign(state,route)})
  mount(defineComponent({setup(){useWorkspaceRoute(()=>state,restore,()=>locked);return()=>h('div')}}))
  await flushPromises();expect(state.nav).toBe('sources')
  state.nav='conversations';await flushPromises()
  expect(window.location.hash).toContain('/conversations')
  window.history.replaceState(null,'','#/sources?project=project-1&source=source-1')
  window.dispatchEvent(new PopStateEvent('popstate'));await flushPromises()
  expect(state.nav).toBe('sources')
  locked=true
  const count=restore.mock.calls.length
  window.history.replaceState(null,'','#/projects')
  window.dispatchEvent(new PopStateEvent('popstate'));await flushPromises()
  expect(restore).toHaveBeenCalledTimes(count);expect(window.location.hash).toContain('/sources')
})
it('fences delayed restoration when the user explicitly changes workspace',async()=>{
  let release!:()=>void
  const pending=new Promise<void>(resolve=>{release=resolve})
  const state=reactive<WorkspaceRoute>({nav:'workbench'})
  let controller!:ReturnType<typeof useWorkspaceRoute>
  mount(defineComponent({setup(){controller=useWorkspaceRoute(()=>state,async(_route,current)=>{
    await pending;if(current())state.nav='sources'
  },()=>false);return()=>h('div')}}))
  controller.cancelRouteRestore();state.nav='projects';release();await flushPromises()
  expect(state.nav).toBe('projects')
})
it('keeps unavailable deep links visible for explicit retry',async()=>{
  const state=reactive<WorkspaceRoute>({nav:'workbench'});let controller!:ReturnType<typeof useWorkspaceRoute>
  const restore=vi.fn().mockRejectedValueOnce(new Error('Project inaccessible')).mockResolvedValueOnce(undefined)
  mount(defineComponent({setup(){controller=useWorkspaceRoute(()=>state,restore,()=>false);return()=>h('div')}}))
  await flushPromises();expect(controller.routeError.value).toBe('Project inaccessible')
  await controller.retryRoute();expect(controller.routeError.value).toBe('')
})

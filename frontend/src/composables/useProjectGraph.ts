import { onScopeDispose, ref, watch } from 'vue'
import { getEntityDetail, getProjectGraph, getRelationshipDetail } from '../api/knowledgeAtlas'
import type { EntityDetail, ProjectGraphData, RelationshipDetail } from '../types'

export function useProjectGraph(context: () => { projectId: string | undefined; active: boolean },
  errorMessage: (error: unknown) => string, clearHistory: () => void, onEntityLoaded: () => void) {
  let disposed = false
  const realGraph = ref<ProjectGraphData | null>(null)
  const realEntityDetail = ref<EntityDetail | null>(null)
  const realRelationshipDetail = ref<RelationshipDetail | null>(null)
  const graphLoading = ref(false)
  const graphDetailLoading = ref(false)
  const graphError = ref('')
  const graphDetailError = ref('')
  const graphSelectedId = ref('')
  const graphSelectionKind = ref<'entity' | 'relationship'>('entity')
  const graphCenter = ref('')
  const graphType = ref('')
  const graphDepth = ref(1)
  const graphValidAt = ref('')
  let graphRequest = 0, graphDetailRequest = 0
  function clearProjectGraph() {
    graphRequest++; graphDetailRequest++
    realGraph.value = null
    realEntityDetail.value = realRelationshipDetail.value = null
    graphSelectedId.value = graphCenter.value = graphType.value = ''
    graphLoading.value = graphDetailLoading.value = false
    graphError.value = graphDetailError.value = ''
  }
  async function loadRealGraph(center = graphCenter.value) {
    const projectId = context().projectId
    if (disposed || !context().active || !projectId) return
    const request = ++graphRequest
    graphDetailRequest++
    graphLoading.value = true
    graphDetailLoading.value = false
    graphError.value = graphDetailError.value = ''
    realGraph.value = null
    realEntityDetail.value = null
    realRelationshipDetail.value = null
    graphCenter.value = center
    try {
      const result = await getProjectGraph(projectId, { centerId: center || undefined, depth: graphDepth.value, types: graphType.value, validAt: graphValidAt.value })
      if (request !== graphRequest || context().projectId !== projectId) return
      realGraph.value = result
      const selected = result.nodes.find(item => item.id === graphSelectedId.value) ?? result.nodes[0]
      graphSelectedId.value = selected?.id ?? ''
      if (selected) await selectGraphEntity(selected.id)
    } catch (error) {
      if (request === graphRequest) graphError.value = errorMessage(error)
    } finally {
      if (request === graphRequest) graphLoading.value = false
    }
  }

  async function selectGraphEntity(id: string) {
    if (disposed || !context().active || !context().projectId) return
    clearHistory()
    if (!realGraph.value?.nodes.some(item => item.id === id)) {
      graphType.value = ''
      await loadRealGraph(id)
      return
    }
    const request = ++graphDetailRequest
    graphSelectedId.value = id
    graphSelectionKind.value = 'entity'
    graphDetailLoading.value = true
    graphDetailError.value = ''
    realEntityDetail.value = realRelationshipDetail.value = null
    try {
      const result = await getEntityDetail(id, graphValidAt.value)
      if (result.entity.project_id !== context().projectId) throw new Error('知识不属于当前项目。')
      if (request === graphDetailRequest) { realEntityDetail.value = result; onEntityLoaded() }
    } catch (error) {
      if (request === graphDetailRequest) graphDetailError.value = errorMessage(error)
    } finally {
      if (request === graphDetailRequest) graphDetailLoading.value = false
    }
  }

  async function selectGraphRelationship(id: string) {
    if (disposed || !context().active || !context().projectId) return
    clearHistory()
    const request = ++graphDetailRequest
    graphSelectedId.value = id
    graphSelectionKind.value = 'relationship'
    graphDetailLoading.value = true
    graphDetailError.value = ''
    realEntityDetail.value = realRelationshipDetail.value = null
    try {
      const result = await getRelationshipDetail(id, graphValidAt.value)
      if (result.relationship.project_id !== context().projectId) throw new Error('关系不属于当前项目。')
      if (request === graphDetailRequest) realRelationshipDetail.value = result
    } catch (error) {
      if (request === graphDetailRequest) graphDetailError.value = errorMessage(error)
    } finally {
      if (request === graphDetailRequest) graphDetailLoading.value = false
    }
  }

  function retryGraphDetail() {
    if (graphSelectionKind.value === 'entity') void selectGraphEntity(graphSelectedId.value)
    else void selectGraphRelationship(graphSelectedId.value)
  }

  function filterGraph(type: string) { graphType.value = type; void loadRealGraph('') }
  function setGraphDepth(depth: number) { graphDepth.value = depth; void loadRealGraph() }


  watch(() => [context().projectId, context().active, graphValidAt.value], clearProjectGraph, { flush:'sync' })
  onScopeDispose(() => { disposed = true; clearProjectGraph() })
  return { realGraph, realEntityDetail, realRelationshipDetail, graphLoading, graphDetailLoading, graphError, graphDetailError,
    graphSelectedId, graphSelectionKind, graphCenter, graphType, graphDepth, graphValidAt,
    clearProjectGraph, loadRealGraph, selectGraphEntity, selectGraphRelationship, retryGraphDetail, filterGraph, setGraphDepth }
}

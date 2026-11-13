import { onScopeDispose, ref, watch } from 'vue'
import { getEntityDetail, getNeo4jGraph, getProjectGraph, getRelationshipDetail, syncNeo4jGraph } from '../api/knowledgeAtlas'
import type { EntityDetail, GraphBackend, Neo4jSnapshot, ProjectGraphData, RelationshipDetail } from '../types'

export function useProjectGraph(context: () => { projectId: string | undefined; active: boolean; relations?: boolean },
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
  const graphBackend = ref<GraphBackend>('postgresql')
  const neo4jSnapshot = ref<Neo4jSnapshot | null>(null)
  const neo4jSyncing = ref(false)
  const neo4jSyncError = ref('')
  let graphRequest = 0, graphDetailRequest = 0
  function clearProjectGraph() {
    graphRequest++; graphDetailRequest++
    realGraph.value = null
    realEntityDetail.value = realRelationshipDetail.value = null
    graphSelectedId.value = graphCenter.value = graphType.value = ''
    graphLoading.value = graphDetailLoading.value = false
    graphError.value = graphDetailError.value = ''
    neo4jSnapshot.value = null
    neo4jSyncError.value = ''
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
      const options = { centerId: center || undefined, depth: graphDepth.value, types: graphType.value }
      const snapshot = graphBackend.value === 'neo4j' ? await getNeo4jGraph(projectId, options) : null
      const result = snapshot ?? await getProjectGraph(projectId, { ...options, validAt: graphValidAt.value })
      if (request !== graphRequest || context().projectId !== projectId) return
      neo4jSnapshot.value = snapshot && { valid_at: snapshot.valid_at, node_count: snapshot.node_count, edge_count: snapshot.edge_count }
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

  function selectGraphBackend(backend: GraphBackend) {
    if (disposed || !context().active || context().relations === false || neo4jSyncing.value || backend === graphBackend.value) return
    clearHistory()
    if (backend === 'neo4j') graphValidAt.value = ''
    graphBackend.value = backend
    clearProjectGraph()
    void loadRealGraph('')
  }

  async function syncGraphToNeo4j() {
    const { projectId, active, relations } = context()
    if (disposed || !active || relations === false || !projectId || graphBackend.value !== 'neo4j' || neo4jSyncing.value) return
    const request = graphRequest
    const isCurrent = () => !disposed && request === graphRequest && context().projectId === projectId
    neo4jSyncing.value = true
    neo4jSyncError.value = ''
    try {
      const snapshot = await syncNeo4jGraph(projectId)
      if (isCurrent()) {
        neo4jSnapshot.value = snapshot
        await loadRealGraph('')
      }
    } catch (error) {
      if (isCurrent()) neo4jSyncError.value = errorMessage(error)
    } finally {
      neo4jSyncing.value = false
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
      const result = await getEntityDetail(id, neo4jSnapshot.value?.valid_at ?? graphValidAt.value)
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
      const result = await getRelationshipDetail(id, neo4jSnapshot.value?.valid_at ?? graphValidAt.value)
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


  watch([() => context().projectId, () => context().active], () => {
    graphBackend.value = 'postgresql'
    clearProjectGraph()
  }, { flush: 'sync' })
  watch(graphValidAt, () => {
    graphBackend.value = 'postgresql'
    clearProjectGraph()
  }, { flush: 'sync' })
  watch(() => context().relations, relations => {
    if (relations === false && graphBackend.value === 'neo4j') {
      graphBackend.value = 'postgresql'
      clearProjectGraph()
      void loadRealGraph('')
    }
  }, { flush: 'sync' })
  onScopeDispose(() => { disposed = true; clearProjectGraph() })
  return { realGraph, realEntityDetail, realRelationshipDetail, graphLoading, graphDetailLoading, graphError, graphDetailError,
    graphSelectedId, graphSelectionKind, graphCenter, graphType, graphDepth, graphValidAt,
    graphBackend, neo4jSnapshot, neo4jSyncing, neo4jSyncError, selectGraphBackend, syncGraphToNeo4j,
    clearProjectGraph, loadRealGraph, selectGraphEntity, selectGraphRelationship, retryGraphDetail, filterGraph, setGraphDepth }
}

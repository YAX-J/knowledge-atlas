<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppHeader from './components/AppHeader.vue'
import SideRail from './components/SideRail.vue'
import KnowledgeGraph from './components/KnowledgeGraph.vue'
import InsightPanel from './components/InsightPanel.vue'
import TimelineBar from './components/TimelineBar.vue'
import { edges, evidences, nodes, nodeTypeLabels, timelinePoints } from './mock/data'
import type { NodeType } from './types'

const selectedId = ref('event-driven')
const activeNav = ref('graph')
const timelineIndex = ref(timelinePoints.length - 1)
const panelOpen = ref(true)
const filterOpen = ref(false)
const allTypes = Object.keys(nodeTypeLabels) as NodeType[]
const visibleTypes = ref<NodeType[]>([...allTypes])

const selectedNode = computed(() => nodes.find((node) => node.id === selectedId.value) ?? nodes[0])
const currentDate = computed(() => timelinePoints[timelineIndex.value]?.date ?? timelinePoints.at(-1)!.date)
const timeFilteredNodes = computed(() => nodes.filter((node) => node.validFrom <= currentDate.value))
const visibleGraphNodes = computed(() => timeFilteredNodes.value.filter((node) => visibleTypes.value.includes(node.type)))

function selectNode(id: string) {
  selectedId.value = id
  panelOpen.value = true
}

function changeNav(value: string) {
  if (value === 'filter') {
    filterOpen.value = !filterOpen.value
    return
  }
  activeNav.value = value
  if (value !== 'graph') {
    const labels: Record<string, string> = { projects: '项目视图', sources: '资料来源', questions: '问答记录' }
    ElMessage({ message: `${labels[value]}将在下一阶段接入，目前展示知识图谱原型。`, type: 'info' })
    activeNav.value = 'graph'
  }
}

function toggleType(type: NodeType) {
  if (visibleTypes.value.includes(type)) {
    if (visibleTypes.value.length === 1) return
    visibleTypes.value = visibleTypes.value.filter((item) => item !== type)
  } else {
    visibleTypes.value = [...visibleTypes.value, type]
  }
  ensureVisibleSelection()
}

function ensureVisibleSelection(date = currentDate.value) {
  const availableNodes = nodes.filter((node) =>
    node.validFrom <= date && visibleTypes.value.includes(node.type),
  )
  if (!availableNodes.some((node) => node.id === selectedId.value) && availableNodes[0]) {
    selectedId.value = availableNodes[0].id
  }
}

function setTimeline(value: number) {
  timelineIndex.value = value
  ensureVisibleSelection(timelinePoints[value]!.date)
}
</script>

<template>
  <div class="app-shell">
    <AppHeader :nodes="nodes" :selected-id="selectedId" @select="selectNode" />
    <SideRail :active="activeNav" @change="changeNav" />

    <main class="atlas-main" :class="{ 'panel-collapsed': !panelOpen }">
      <section class="graph-workspace">
        <div class="workspace-title">
          <div>
            <h1>你的技术宇宙，正在成形</h1>
            <p>节点大小代表复用频率，连线亮度代表最近关联。</p>
          </div>
          <div class="workspace-stats" aria-label="图谱统计">
            <span><strong>{{ visibleGraphNodes.length }}</strong> 个节点</span>
            <span><strong>{{ edges.length }}</strong> 条关联</span>
          </div>
        </div>

        <div v-if="filterOpen" class="filter-popover">
          <div><strong>显示知识类型</strong><button type="button" @click="filterOpen = false">完成</button></div>
          <label v-for="type in allTypes" :key="type">
            <input type="checkbox" :checked="visibleTypes.includes(type)" @change="toggleType(type)" />
            <i :class="`dot-${type}`" />{{ nodeTypeLabels[type] }}
          </label>
        </div>

        <KnowledgeGraph
          :nodes="timeFilteredNodes"
          :edges="edges"
          :selected-id="selectedId"
          :visible-types="visibleTypes"
          @select="selectNode"
        />

        <TimelineBar :model-value="timelineIndex" :points="timelinePoints" @update:model-value="setTimeline" />
      </section>

      <InsightPanel
        v-if="panelOpen"
        :node="selectedNode"
        :nodes="nodes"
        :edges="edges"
        :evidences="evidences"
        @select="selectNode"
        @close="panelOpen = false"
      />

      <button v-else class="reopen-panel" type="button" @click="panelOpen = true">
        查看 {{ selectedNode.label }}
      </button>
    </main>
  </div>
</template>

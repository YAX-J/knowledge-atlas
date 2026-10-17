<script setup lang="ts">
import { computed, ref } from 'vue'
import { Minus, Plus, RefreshRight } from '@element-plus/icons-vue'
import type { KnowledgeEdge, KnowledgeNode, NodeType } from '../types'
import { nodeTypeLabels } from '../mock/data'

const props = defineProps<{
  nodes: KnowledgeNode[]
  edges: KnowledgeEdge[]
  selectedId: string
  visibleTypes: NodeType[]
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const zoom = ref(1)
const stage = ref({ x: 0, y: 0 })

const nodeMap = computed(() => new Map(props.nodes.map((node) => [node.id, node])))
const filteredNodes = computed(() => props.nodes.filter((node) => props.visibleTypes.includes(node.type)))
const visibleIds = computed(() => new Set(filteredNodes.value.map((node) => node.id)))
const filteredEdges = computed(() => props.edges.filter((edge) => visibleIds.value.has(edge.source) && visibleIds.value.has(edge.target)))

function point(id: string) {
  return nodeMap.value.get(id) ?? { x: 0, y: 0 }
}

function nodeClass(node: KnowledgeNode) {
  return [
    `node-${node.type}`,
    { selected: node.id === props.selectedId, muted: props.selectedId && !isRelated(node.id) },
  ]
}

function isRelated(id: string) {
  if (id === props.selectedId) return true
  return props.edges.some((edge) =>
    (edge.source === props.selectedId && edge.target === id) ||
    (edge.target === props.selectedId && edge.source === id),
  )
}

function diamondPoints(node: KnowledgeNode) {
  const width = node.size * 1.22
  const height = node.size * 0.82
  return `${node.x},${node.y - height} ${node.x + width},${node.y} ${node.x},${node.y + height} ${node.x - width},${node.y}`
}

function adjustZoom(delta: number) {
  zoom.value = Math.min(1.25, Math.max(0.75, Number((zoom.value + delta).toFixed(2))))
}

function resetView() {
  zoom.value = 1
  stage.value = { x: 0, y: 0 }
}
</script>

<template>
  <div class="graph-shell">
    <div class="graph-legend" aria-label="知识类型图例">
      <span v-for="type in visibleTypes" :key="type" :class="`legend-${type}`">
        <i />{{ nodeTypeLabels[type] }}
      </span>
    </div>

    <svg class="knowledge-graph" viewBox="0 -120 1000 900" role="img" aria-label="个人知识图谱">
      <defs>
        <filter id="selected-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="8" result="blur" />
          <feFlood flood-color="#9d2f58" flood-opacity="0.18" />
          <feComposite in2="blur" operator="in" />
          <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <g :transform="`translate(${stage.x} ${stage.y}) scale(${zoom})`" class="graph-stage">
        <circle class="orbit orbit-one" cx="500" cy="390" r="185" />
        <circle class="orbit orbit-two" cx="500" cy="390" r="275" />
        <circle class="orbit orbit-three" cx="500" cy="390" r="355" />

        <g class="edges">
          <g v-for="edge in filteredEdges" :key="edge.id" :class="{ highlighted: edge.highlighted || edge.source === selectedId || edge.target === selectedId }">
            <line
              :x1="point(edge.source).x"
              :y1="point(edge.source).y"
              :x2="point(edge.target).x"
              :y2="point(edge.target).y"
            />
            <text
              :x="(point(edge.source).x + point(edge.target).x) / 2"
              :y="(point(edge.source).y + point(edge.target).y) / 2 - 8"
            >{{ edge.label }}</text>
          </g>
        </g>

        <g
          v-for="node in filteredNodes"
          :key="node.id"
          class="knowledge-node"
          :class="nodeClass(node)"
          :transform="`translate(${node.x} ${node.y})`"
          role="button"
          tabindex="0"
          :aria-label="`${nodeTypeLabels[node.type]}：${node.label}`"
          @click="emit('select', node.id)"
          @keydown.enter="emit('select', node.id)"
          @keydown.space.prevent="emit('select', node.id)"
        >
          <template v-if="node.type === 'project' || node.type === 'code'">
            <rect :x="-node.size" :y="-node.size * 0.55" :width="node.size * 2" :height="node.size * 1.1" rx="8" />
          </template>
          <template v-else-if="node.type === 'decision' || node.type === 'question'">
            <polygon :points="diamondPoints({ ...node, x: 0, y: 0 })" />
          </template>
          <template v-else>
            <circle :r="node.size" />
          </template>
          <circle v-if="node.id === selectedId" class="selection-ring" :r="node.size + 13" />
          <text class="node-label" text-anchor="middle" :y="node.type === 'decision' || node.type === 'question' ? -2 : 0">{{ node.label }}</text>
          <text class="node-subtitle" text-anchor="middle" :y="node.type === 'decision' || node.type === 'question' ? 18 : 22">{{ node.subtitle }}</text>
        </g>
      </g>
    </svg>

    <div class="zoom-controls" aria-label="图谱缩放">
      <button type="button" aria-label="放大" @click="adjustZoom(0.1)"><el-icon><Plus /></el-icon></button>
      <span>{{ Math.round(zoom * 100) }}%</span>
      <button type="button" aria-label="缩小" @click="adjustZoom(-0.1)"><el-icon><Minus /></el-icon></button>
      <button type="button" aria-label="重置视图" @click="resetView"><el-icon><RefreshRight /></el-icon></button>
    </div>
  </div>
</template>

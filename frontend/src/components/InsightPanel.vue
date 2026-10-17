<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowRight, Close, Position } from '@element-plus/icons-vue'
import type { Evidence, KnowledgeEdge, KnowledgeNode } from '../types'
import { nodeTypeLabels } from '../mock/data'

const props = defineProps<{
  node: KnowledgeNode
  nodes: KnowledgeNode[]
  edges: KnowledgeEdge[]
  evidences: Evidence[]
}>()

const emit = defineEmits<{
  select: [id: string]
  close: []
}>()

const asking = ref(false)
const question = ref('')
const answer = ref('')
const loading = ref(false)
const selectedEvidence = ref<string | null>(null)

const sources = computed(() => props.node.evidenceIds
  .map((id) => props.evidences.find((item) => item.id === id))
  .filter((item): item is Evidence => Boolean(item)))

const related = computed(() => props.edges.flatMap((edge) => {
  if (edge.source === props.node.id) return [{ edge, node: props.nodes.find((item) => item.id === edge.target) }]
  if (edge.target === props.node.id) return [{ edge, node: props.nodes.find((item) => item.id === edge.source) }]
  return []
}).filter((item): item is { edge: KnowledgeEdge; node: KnowledgeNode } => Boolean(item.node)))

watch(() => props.node.id, () => {
  asking.value = false
  answer.value = ''
  selectedEvidence.value = null
})

function ask() {
  if (!question.value.trim() || loading.value) return
  loading.value = true
  answer.value = ''
  window.setTimeout(() => {
    answer.value = `${props.node.label}在当前图谱中与 ${related.value.slice(0, 2).map((item) => item.node.label).join('、')} 直接相关。现有证据表明：${sources.value[0]?.excerpt ?? props.node.description}`
    loading.value = false
  }, 800)
}

function kindLabel(kind: Evidence['kind']) {
  return { md: 'MD', java: 'JAVA', adr: 'ADR', git: 'GIT' }[kind]
}
</script>

<template>
  <aside class="insight-panel" aria-label="知识详情">
    <button class="panel-close" type="button" aria-label="关闭知识详情" @click="emit('close')"><el-icon><Close /></el-icon></button>
    <div class="panel-kicker">
      <span>知识透镜</span>
      <strong>{{ nodeTypeLabels[node.type] }}</strong>
    </div>
    <h2>{{ node.label }}</h2>
    <p class="node-description">{{ node.description }}</p>
    <dl class="node-meta">
      <div><dt>所属项目</dt><dd>{{ node.project }}</dd></div>
      <div><dt>可信度</dt><dd>{{ Math.round(node.confidence * 100) }}%</dd></div>
      <div><dt>首次记录</dt><dd>{{ node.validFrom }}</dd></div>
    </dl>

    <section class="panel-section">
      <div class="section-heading"><h3>证据来源</h3><span>{{ sources.length }}</span></div>
      <div class="evidence-list">
        <button
          v-for="source in sources"
          :key="source.id"
          type="button"
          :class="{ expanded: selectedEvidence === source.id }"
          @click="selectedEvidence = selectedEvidence === source.id ? null : source.id"
        >
          <span class="file-kind">{{ kindLabel(source.kind) }}</span>
          <span class="file-copy"><strong>{{ source.title }}</strong><small>{{ source.location }} · {{ source.updatedAt }}</small></span>
          <span v-if="selectedEvidence === source.id" class="evidence-excerpt">“{{ source.excerpt }}”</span>
        </button>
      </div>
    </section>

    <section class="panel-section">
      <div class="section-heading"><h3>关键关联</h3><span>{{ related.length }}</span></div>
      <div class="relation-list">
        <button v-for="item in related.slice(0, 4)" :key="item.edge.id" type="button" @click="emit('select', item.node.id)">
          <i :class="`dot-${item.node.type}`" />
          <span>{{ item.node.label }}</span>
          <small>{{ item.edge.label }}</small>
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>
    </section>

    <div class="ask-area" :class="{ open: asking }">
      <button v-if="!asking" class="ask-trigger" type="button" @click="asking = true">
        围绕这个节点继续提问 <el-icon><Position /></el-icon>
      </button>
      <form v-else @submit.prevent="ask">
        <label for="follow-up">继续追问</label>
        <textarea id="follow-up" v-model="question" rows="2" :placeholder="`例如：${node.label}在哪些代码中实现？`" />
        <button type="submit" :disabled="!question.trim() || loading">{{ loading ? '正在核查证据…' : '基于证据回答' }}</button>
        <p v-if="answer" class="mock-answer">{{ answer }}<small>模拟回答 · 引用了 {{ Math.min(2, sources.length) }} 条证据</small></p>
      </form>
    </div>
  </aside>
</template>

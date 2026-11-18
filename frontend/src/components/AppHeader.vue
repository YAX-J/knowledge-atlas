<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ChatDotRound, Collection, Search } from '@element-plus/icons-vue'
import { deckCommands } from '../deckNavigation'
import type { KnowledgeNode } from '../types'

const props = defineProps<{
  nodes: KnowledgeNode[]
  selectedId: string
  graphActive: boolean
  projectName?: string
  projectId?: string
  projectOptions?: readonly { id: string; name: string }[]
  projectSwitchDisabled?: boolean
  active?: string
  focusOnly?: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  search: [query: string]
  navigate: [id: string]
  selectProject: [id: string]
  toggleFocus: []
}>()

type PaletteItem = { id: string; title: string; detail: string; kind: 'command' | 'demo' | 'search' }
const query = ref('')
const scope = ref<'all' | 'command' | 'knowledge'>('all')
const selected = ref(0)
const dialog = ref<HTMLDialogElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const commandTrigger = ref<HTMLButtonElement | null>(null)
let previousFocus: HTMLElement | null = null

const context = computed(() => deckCommands.find(item => item.id === props.active) ?? deckCommands[0])
const scopes = [
  { id: 'all', label: '全部' }, { id: 'command', label: '命令' }, { id: 'knowledge', label: '知识' },
] as const

const results = computed<PaletteItem[]>(() => {
  const keyword = query.value.trim().toLowerCase()
  const items: PaletteItem[] = []
  if (scope.value !== 'knowledge') {
    for (const item of deckCommands) {
      if (`${item.label} ${item.caption} ${item.id}`.toLowerCase().includes(keyword)) {
        items.push({ id: item.id, title: `打开${item.label}`, detail: item.caption, kind: 'command' })
      }
    }
  }
  if (!keyword || scope.value === 'command') return items
  if (props.graphActive) {
    for (const node of props.nodes.filter(node => `${node.label} ${node.description} ${node.project}`.toLowerCase().includes(keyword)).slice(0, 5)) {
      items.push({ id: node.id, title: node.label, detail: `${node.project} · ${node.subtitle}`, kind: 'demo' })
    }
  } else {
    items.push({ id: 'query', title: `检索「${query.value.trim()}」`, detail: '当前项目 · BM25 + 来源位置', kind: 'search' })
  }
  return items
})
watch([query, scope], () => { selected.value = 0 })

function openPalette() {
  if (!dialog.value || dialog.value.open) return
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  query.value = ''
  scope.value = 'all'
  selected.value = 0
  dialog.value.showModal()
  searchInput.value?.focus()
}

function shortcut(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    openPalette()
  }
}
onMounted(() => window.addEventListener('keydown', shortcut))
onUnmounted(() => window.removeEventListener('keydown', shortcut))

function restoreFocus() {
  const target = previousFocus?.isConnected ? previousFocus : commandTrigger.value
  if (target === document.body) commandTrigger.value?.focus()
  else target?.focus()
  previousFocus = null
}

function step(offset: number) {
  if (!results.value.length) return
  selected.value = (selected.value + offset + results.value.length) % results.value.length
  void nextTick(() => document.getElementById(`deck-option-${selected.value}`)?.scrollIntoView?.({ block: 'nearest' }))
}

function choose(item = results.value[selected.value]) {
  if (!item) return
  if (dialog.value?.open) {
    dialog.value.close()
    restoreFocus()
  }
  if (item.kind === 'command') emit('navigate', item.id)
  else if (item.kind === 'demo') emit('select', item.id)
  else emit('search', query.value.trim())
}

function cancel() {
  dialog.value?.close()
  restoreFocus()
}
</script>

<template>
  <header class="app-header">
    <div class="deck-context">
      <strong>{{ context?.label }}</strong><span class="context-caption">{{ context?.caption }}</span>
    </div>
    <label v-if="projectOptions?.length && !graphActive" class="context-project context-project-select" :title="projectName">
      <Collection aria-hidden="true" />
      <select :value="projectId ?? ''" :disabled="projectSwitchDisabled" aria-label="当前图谱项目"
        @change="emit('selectProject', ($event.target as HTMLSelectElement).value)">
        <option value="" disabled>选择项目</option>
        <option v-for="item in projectOptions" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select>
    </label>
    <span v-else class="context-project" :title="projectName">
      <Collection aria-hidden="true" /><span>{{ graphActive ? '独立演示' : projectName || '未选择项目' }}</span>
    </span>
    <div class="context-actions">
      <slot />
      <button class="deck-button focus-button" type="button" :aria-pressed="Boolean(focusOnly)" @click="emit('toggleFocus')">
        <ChatDotRound aria-hidden="true" />{{ focusOnly ? '退出专注' : '专注提问' }}
      </button>
      <button ref="commandTrigger" class="deck-button" type="button" aria-haspopup="dialog" @click="openPalette">
        <Search aria-hidden="true" />命令 <kbd>Ctrl K</kbd>
      </button>
    </div>
    <dialog ref="dialog" class="deck-palette" aria-label="命令面板" @cancel.prevent="cancel" @click.self="cancel">
      <div class="palette-content">
        <div class="palette-search">
          <Search aria-hidden="true" />
          <input ref="searchInput" v-model="query" type="search" maxlength="200"
            placeholder="搜索命令或当前项目知识…" aria-label="搜索命令或知识" aria-controls="deck-results"
            @keydown.down.prevent="step(1)" @keydown.up.prevent="step(-1)" @keydown.enter.prevent="choose()">
          <button class="deck-button" type="button" aria-label="关闭命令面板" @click="cancel">Esc</button>
        </div>
        <div class="palette-scopes" role="group" aria-label="搜索范围">
          <button v-for="item in scopes" :key="item.id" class="deck-button" type="button" :aria-pressed="scope === item.id" @click="scope = item.id">{{ item.label }}</button>
        </div>
        <ul id="deck-results" class="palette-results" aria-label="可用命令和知识">
          <li v-for="(item, index) in results" :key="`${item.kind}-${item.id}`">
            <button :id="`deck-option-${index}`" type="button" :class="{ 'is-selected': index === selected }"
              @focus="selected = index" @click="choose(item)">
              <span>{{ item.title }}</span><small>{{ item.detail }}</small>
            </button>
          </li>
          <li v-if="!results.length" class="palette-empty">{{ query ? '没有匹配项，试试其他关键词或范围。' : '输入关键词开始检索。' }}</li>
        </ul>
        <footer>↑ ↓ 选择 · Enter 打开 · Esc 关闭</footer>
      </div>
    </dialog>
  </header>
</template>

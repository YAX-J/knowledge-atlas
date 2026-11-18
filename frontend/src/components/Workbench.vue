<script setup lang="ts">
import { computed, nextTick, ref, shallowRef } from 'vue'
import { ArrowRight, Clock, DataAnalysis, Files, FullScreen, Link, List, Minus, Plus, TrendCharts } from '@element-plus/icons-vue'
import type { ApiProject, ApiProjectList, SourceListItem } from '../api/knowledgeAtlas'
import type { ProjectOverview } from '../types'

const props = defineProps<{
  project: ApiProject | null
  projects: ApiProjectList | null
  overview: ProjectOverview | null
  recentSources?: SourceListItem[]
  sourcesLoading?: boolean
  sourcesError?: string
  locked?: boolean
  loading: boolean
  error: string
}>()
const emit = defineEmits<{
  navigate: [value: string]
  selectProject: [value: ApiProject]
  openSource: [item: SourceListItem]
  refresh: []
}>()

const modules = [
  { id: 'pulse', title: '知识脉搏', description: '近 14 天 · 当前资料列表的导入记录', icon: TrendCharts, color: 'indigo' },
  { id: 'stats', title: '四项读数', description: '已确认知识 · 资料解析 · 待审核', icon: DataAnalysis, color: 'teal' },
  { id: 'projects', title: '项目概览', description: '切换当前项目', icon: Files, color: 'violet' },
  { id: 'todo', title: '待办', description: '继续处理当前项目', icon: List, color: 'orange' },
  { id: 'activity', title: '最近动态', description: '当前资料列表的最近更新', icon: Clock, color: 'pink' },
  { id: 'reuse', title: '知识复用', description: '从已确认知识和历史会话找回证据', icon: Link, color: 'teal' },
] as const

type Module = typeof modules[number]
type ModuleId = Module['id']

const order = shallowRef<readonly Module[]>(modules)
const collapsed = ref<ModuleId[]>([])
const expanded = ref<ModuleId | null>(null)
const drag = ref<ModuleId | null>(null)
const dropTarget = ref<ModuleId | null>(null)
const deck = ref<HTMLElement | null>(null)
const allCollapsed = computed(() => collapsed.value.length === modules.length)

const parseCoverage = computed(() => props.overview?.sources ? Math.round(100 * props.overview.ready_sources / props.overview.sources) : null)
const stats = computed(() => [
  { label: '正式实体', value: props.overview?.entities ?? '—', note: '当前有效' },
  { label: '正式关系', value: props.overview?.relationships ?? '—', note: '当前有效' },
  { label: '资料解析', value: parseCoverage.value === null ? '—' : `${parseCoverage.value}%`,
    note: props.overview ? `${props.overview.sources} / ${props.overview.ready_sources} 份` : '全部 / 已解析' },
  { label: '待确认', value: props.overview?.pending_reviews ?? '—', note: '候选知识' },
])
const todos = computed(() => [
  { count: props.overview?.pending_reviews, label: '候选待确认', description: '核对原文，确认实体或关系', route: 'review', color: 'pink' },
  { count: props.overview?.pending_tasks, label: '处理中的任务', description: '查看资料处理进度', route: 'sources', color: 'orange' },
  { count: props.overview ? props.overview.sources - props.overview.ready_sources : undefined, label: '未完成解析', description: '打开资料库查看状态', route: 'sources', color: 'teal' },
])
const activities = computed(() => [...(props.recentSources ?? [])]
  .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)).slice(0, 5))
const statusLabels: Record<SourceListItem['status'], string> = {
  uploaded: '已导入', processing: '解析中', ready: '已解析', failed: '解析失败',
}
const dayFormat = new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' })
const activityFormat = new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
const pulse = computed(() => {
  const today = new Date()
  const days = Array.from({ length: 14 }, (_, index) => {
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 13 + index)
    const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1)
    const count = (props.recentSources ?? []).filter(item => {
      const created = Date.parse(item.created_at)
      return created >= start.getTime() && created < end.getTime()
    }).length
    return { date: dayFormat.format(start), count }
  })
  return {
    days,
    total: days.reduce((total, day) => total + day.count, 0),
    max: Math.max(1, ...days.map(day => day.count)),
  }
})

function toggle(id: ModuleId) {
  collapsed.value = collapsed.value.includes(id) ? collapsed.value.filter(item => item !== id) : [...collapsed.value, id]
}

function toggleExpanded(id: ModuleId) {
  expanded.value = expanded.value === id ? null : id
  if (expanded.value && collapsed.value.includes(id)) toggle(id)
  void nextTick(() => deck.value?.querySelector<HTMLButtonElement>(`[data-expand="${id}"]`)?.focus())
}

function toggleAll() {
  expanded.value = null
  collapsed.value = allCollapsed.value ? [] : modules.map(item => item.id)
}

function resetLayout() {
  order.value = modules
  expanded.value = null
  collapsed.value = []
}

function move(id: ModuleId, offset: number) {
  const items = [...order.value]
  const from = items.findIndex(item => item.id === id)
  const to = from + offset
  if (to < 0 || to >= items.length || expanded.value) return
  const [item] = items.splice(from, 1)
  if (!item) return
  items.splice(to, 0, item)
  order.value = items
}

function startDrag(event: DragEvent, id: ModuleId) {
  if (!event.dataTransfer) return
  drag.value = id
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', id)
}

function dragOver(event: DragEvent, target: ModuleId) {
  if (!drag.value || drag.value === target) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dropTarget.value = target
}

function finishDrag() {
  drag.value = dropTarget.value = null
}

function drop(target: ModuleId) {
  if (drag.value) {
    const from = order.value.findIndex(item => item.id === drag.value)
    const to = order.value.findIndex(item => item.id === target)
    move(drag.value, to - from)
  }
  finishDrag()
}

function toggleLargeCard() {
  if (expanded.value) toggleExpanded(expanded.value)
  else if (order.value[0]) toggleExpanded(order.value[0].id)
}

defineExpose({ resetLayout, toggleAll, toggleLargeCard, allCollapsed, expanded })
</script>

<template>
  <main ref="deck" class="workbench-page" aria-label="工作台" @keydown.esc="expanded && toggleExpanded(expanded)">
    <div v-if="error" role="alert" class="deck-notice deck-notice-error">
      {{ error }} <button class="deck-button" type="button" @click="emit('refresh')">重新读取工作台</button>
    </div>
    <div v-else-if="loading" class="deck-notice" role="status">正在读取项目进度…</div>
    <div class="bento-grid" :class="{ 'bento-expanded': expanded }">
      <article v-for="module in order" v-show="!expanded || expanded === module.id" :key="module.id"
        class="bento-module" :class="[`deck-${module.color}`, { 'is-drop-target': dropTarget === module.id, 'is-dragging': drag === module.id }]"
        :aria-labelledby="`bento-${module.id}`" @dragover="dragOver($event, module.id)" @drop.prevent="drop(module.id)">
        <header class="bento-head">
          <div class="bento-handle" :draggable="!expanded" @dragstart="startDrag($event, module.id)" @dragend="finishDrag">
            <span class="bento-icon" aria-hidden="true"><component :is="module.icon" /></span>
            <div class="bento-titles"><h2 :id="`bento-${module.id}`">{{ module.title }}</h2><p>{{ module.description }}</p></div>
          </div>
          <div class="bento-tools">
            <span v-if="module.id === 'stats'" class="bento-badge">4 项</span>
            <span v-if="module.id === 'projects' && projects" class="bento-badge">{{ projects.total }} 个项目</span>
            <span v-if="module.id === 'activity' && activities.length" class="bento-badge">{{ activities.length }} 条</span>
            <button v-if="!expanded" class="bento-tool" type="button"
              :title="collapsed.includes(module.id) ? '展开模块' : '收起模块（按 Alt + ← 或 → 移动）'"
              :aria-label="`${collapsed.includes(module.id) ? '展开' : '收起'}${module.title}`"
              :aria-expanded="!collapsed.includes(module.id)" :aria-controls="`bento-body-${module.id}`"
              @click="toggle(module.id)" @keydown.alt.left.prevent="move(module.id, -1)" @keydown.alt.right.prevent="move(module.id, 1)">
              <Plus v-if="collapsed.includes(module.id)" /><Minus v-else />
            </button>
            <button class="bento-tool" type="button" :data-expand="module.id"
              :title="expanded ? '返回全部模块' : '放大模块'" :aria-label="expanded ? '返回全部模块' : `放大${module.title}`"
              :aria-pressed="expanded === module.id" @click="toggleExpanded(module.id)"><FullScreen /></button>
          </div>
        </header>
        <div v-show="!collapsed.includes(module.id)" :id="`bento-body-${module.id}`" class="bento-body">
          <template v-if="module.id === 'pulse'">
            <template v-if="overview && !sourcesLoading && !sourcesError">
              <div class="pulse-total"><strong>{{ pulse.total }}</strong><span>近 14 天导入</span></div>
              <div class="pulse-chart" role="img" :aria-label="pulse.days.map(day => `${day.date} 导入 ${day.count} 份`).join('，')">
                <div v-for="(day, index) in pulse.days" :key="day.date" class="pulse-column" :title="`${day.date} · ${day.count} 份`">
                  <div class="pulse-track"><span :style="{ height: `${100 * day.count / pulse.max}%` }"></span></div>
                  <small>{{ index % 3 === 0 || index === pulse.days.length - 1 ? day.date : '' }}</small>
                </div>
              </div>
            </template>
            <div v-else class="bento-empty">{{ sourcesLoading ? '正在读取资料…' : sourcesError || '当前列表近 14 天暂无导入记录。' }}
              <button class="deck-button" type="button" @click="emit('navigate', 'sources')">打开资料库</button>
            </div>
          </template>
          <template v-else-if="module.id === 'stats'">
            <dl class="bento-stats"><div v-for="stat in stats" :key="stat.label">
              <dt>{{ stat.label }}</dt><dd>{{ stat.value }}</dd><small>{{ stat.note }}</small>
            </div></dl>
            <div v-if="parseCoverage !== null" class="deck-meter">
              <span>资料解析覆盖率</span><progress :value="parseCoverage" max="100" :aria-label="`已解析 ${parseCoverage}%`" />
            </div>
            <p class="bento-hint">资料顺序：全部 / 已解析</p>
          </template>
          <template v-else-if="module.id === 'projects'">
            <button v-for="item in projects?.items ?? []" :key="item.id" type="button" class="bento-row project-row"
              :aria-pressed="item.id === project?.id" :disabled="locked" @click="item.id !== project?.id && emit('selectProject', item)">
              <span><strong>{{ item.name }}</strong><small v-if="item.description">{{ item.description }}</small></span>
              <span v-if="item.id === project?.id" class="bento-badge">当前</span>
            </button>
            <div v-if="!projects?.items.length" class="bento-empty">{{ loading ? '正在读取项目…' : '创建项目，开始整理笔记和资料。' }}</div>
            <button class="deck-button" type="button" @click="emit('navigate', 'projects')">管理项目</button>
          </template>
          <template v-else-if="module.id === 'todo'">
            <button v-for="todo in todos" :key="todo.label" type="button" class="bento-row todo-row" :class="`deck-${todo.color}`" @click="emit('navigate', todo.route)">
              <b class="todo-count">{{ todo.count ?? '—' }}</b><span><strong>{{ todo.label }}</strong><small>{{ todo.description }}</small></span><ArrowRight class="row-arrow" />
            </button>
            <button class="bento-row todo-row deck-indigo" type="button" @click="emit('navigate', 'notes')">
              <Files class="todo-count todo-icon" /><span><strong>打开项目笔记</strong><small>续写笔记或从已保存的修订抽取知识</small></span><ArrowRight class="row-arrow" />
            </button>
          </template>
          <template v-else-if="module.id === 'activity'">
            <button v-for="item in activities" :key="item.id" type="button" class="bento-row activity-row" :disabled="locked" @click="emit('openSource', item)">
              <time :datetime="item.updated_at">{{ activityFormat.format(new Date(item.updated_at)) }}</time>
              <i :class="item.status" aria-hidden="true"></i>
              <span><strong>{{ item.relative_path || item.original_name }}</strong><small>{{ statusLabels[item.status] }}</small></span>
            </button>
            <div v-if="!activities.length" class="bento-empty">{{ sourcesLoading ? '正在读取资料…' : sourcesError || '这里会显示导入流程中的资料状态。' }}
              <button class="deck-button" type="button" @click="emit('navigate', 'sources')">查看项目资料</button>
            </div>
          </template>
          <template v-else>
            <button class="bento-row link-row" type="button" @click="emit('navigate', 'search')"><span><strong>检索已确认知识</strong><small>先切换到需要回查的项目，再搜索名称、摘要和原文</small></span><ArrowRight class="row-arrow" /></button>
            <button class="bento-row link-row" type="button" @click="emit('navigate', 'conversations')"><span><strong>打开证据会话</strong><small>找回历史问题、回答与引用</small></span><ArrowRight class="row-arrow" /></button>
            <button class="bento-row link-row" type="button" @click="emit('navigate', 'graph')"><span><strong>浏览知识图谱</strong><small>沿关系和有效期定位已有结论</small></span><ArrowRight class="row-arrow" /></button>
            <button class="deck-button" type="button" @click="emit('navigate', 'demo')">查看独立演示图谱</button>
          </template>
        </div>
      </article>
    </div>
  </main>
</template>

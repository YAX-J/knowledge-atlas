<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { isCodeSource, sourceFileAccept, sourceLanguageHint, sourceTypeForFile, sourceTypeLabel } from '../sourceLanguages'
import type {
  AgentCallAnalysis, ApiProject, ApiProjectList, ApiSource, JavaCodeStructure, ProcessingTask, SourceChunkList, SourceList, SourceListItem, SourceRepository, SourceRepositoryList,
} from '../api/knowledgeAtlas'
import type { IngestionErrors, IngestionLoading } from '../types'

const props = defineProps<{
  view: 'projects' | 'sources'
  projects: ApiProjectList | null
  project: ApiProject | null
  repositories: SourceRepositoryList | null
  sources: SourceList | null
  selectedSourceId: string
  source: ApiSource | null
  task: ProcessingTask | null
  chunks: SourceChunkList | null
  codeStructure: JavaCodeStructure | null
  agentCallAnalysis: AgentCallAnalysis | null
  focusedChunkId?: string
  loading: IngestionLoading
  errors: IngestionErrors
  notice: string
}>()
const emit = defineEmits<{
  create: [input: { name: string; description: string }]
  selectProject: [project: ApiProject]
  projectsPage: [page: number]
  repositoriesPage: [page: number]
  resolveGithub: [input: { remoteUrl: string; localRepositoryId?: string }]
  syncGithub: [input: { repositoryId: string; ref?: string; rescan?: boolean }]
  importGithubActivity: [repositoryId: string]
  snapshots: [repository: SourceRepository]
  sourcesPage: [page: number]
  selectSource: [sourceId: string, taskId: string | null]
  upload: [files: File[]]
  run: []
  refresh: []
  chunksPage: [page: number]
  analyzeCalls: [strategy: 'single_step' | 'tools']
  graph: []
}>()
const name = ref('')
const description = ref('')
const remoteUrl = ref('')
const localRepositoryId = ref('')
const githubRefs = reactive<Record<string, string>>({})
const githubRescans = reactive<Record<string, boolean>>({})
const singleFileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
const fileError = ref('')
const selectionNote = ref('')
const uploadKind = ref<'file' | 'folder' | ''>('')
const agentStrategy = ref<'single_step' | 'tools'>('single_step')
const projectPages = computed(() => Math.max(1, Math.ceil((props.projects?.total ?? 0) / (props.projects?.page_size ?? 20))))
const repositoryPages = computed(() => Math.max(1, Math.ceil((props.repositories?.total ?? 0) / (props.repositories?.page_size ?? 20))))
const sourcePages = computed(() => Math.max(1, Math.ceil((props.sources?.total ?? 0) / (props.sources?.page_size ?? 20))))
const chunkPages = computed(() => Math.max(1, Math.ceil((props.chunks?.total ?? 0) / (props.chunks?.page_size ?? 20))))
const codeSymbolsById = computed(() => new Map((props.codeStructure?.symbols ?? []).map(item => [item.id, item])))
const relatedTypesById = computed(() => new Map((props.codeStructure?.related_types ?? []).map(item => [item.id, item])))
const relatedMethodsById = computed(() => new Map((props.codeStructure?.related_methods ?? []).map(item => [item.id, item])))
const agentTargetsById = computed(() => new Map((props.agentCallAnalysis?.related_symbols ?? []).map(item => [item.id, item])))
const linkableLocalRepositories = computed(() => (
  props.repositories?.items.filter(item => item.kind === 'local_folder' && !item.remote_url) ?? []
))
const locked = computed(() => props.loading.create || props.loading.upload || props.loading.task || props.loading.remote || props.loading.sync || props.loading.activity || props.loading.commit || props.loading.agent)
const statusLabels: Record<string, string> = {
  uploaded: '待解析', processing: '解析中', ready: '已解析', failed: '解析失败',
  queued: '待解析', running: '解析中', succeeded: '已解析', cancelled: '已取消',
}
const kindLabels: Record<string, string> = {
  heading: '标题', paragraph: '段落', list: '列表', code: '代码', comment: '注释', type: '类型', method: '方法',
}
watch(() => props.project?.id, () => {
  fileError.value = ''
  selectionNote.value = ''
  uploadKind.value = ''
  remoteUrl.value = ''
  localRepositoryId.value = ''
})
watch(() => props.loading.upload, (busy, wasBusy) => {
  if (wasBusy && !busy) uploadKind.value = ''
})
watch(() => props.loading.create, (busy, wasBusy) => {
  if (wasBusy && !busy && !props.errors.create) {
    name.value = ''
    description.value = ''
  }
})
watch(() => props.loading.remote, (busy, wasBusy) => {
  if (wasBusy && !busy && !props.errors.remote) {
    remoteUrl.value = ''
    localRepositoryId.value = ''
  }
})

function submitProject() {
  if (name.value.trim() && !props.loading.create) {
    emit('create', { name: name.value.trim(), description: description.value.trim() })
  }
}

function submitGithubRepository() {
  if (remoteUrl.value.trim() && !props.loading.remote) {
    emit('resolveGithub', {
      remoteUrl: remoteUrl.value.trim(),
      localRepositoryId: localRepositoryId.value || undefined,
    })
  }
}

function selectedFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  return files
}

function chooseSingleFile(event: Event) {
  const file = selectedFiles(event)[0]
  if (!file) return
  fileError.value = ''
  selectionNote.value = ''
  if (!sourceTypeForFile(file.name)) {
    fileError.value = `请选择支持的文件：${sourceLanguageHint}。`
    return
  }
  if (!file.size) {
    fileError.value = '文件为空，请选择有内容的文本资料。'
    return
  }
  uploadKind.value = 'file'
  emit('upload', [file])
}

function chooseFolder(event: Event) {
  const selected = selectedFiles(event)
  if (!selected.length) return
  fileError.value = ''
  selectionNote.value = ''
  const files = selected.filter(file => sourceTypeForFile(file.name) && file.size)
  const ignored = selected.length - files.length
  if (!files.length) {
    fileError.value = '这个文件夹中没有可上传的非空 Markdown 或受支持的代码文件。'
    return
  }
  if (files.length > 50) {
    fileError.value = `文件夹中有 ${files.length} 个可上传文件，一次最多上传 50 个。`
    return
  }
  if (ignored) selectionNote.value = `已忽略 ${ignored} 个格式不支持或内容为空的文件。`
  uploadKind.value = 'folder'
  emit('upload', files)
}

function formatSize(bytes: number) {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`
}
function codeSymbolKindLabel(kind: string) {
  return ({ type: '类型', field: '字段/属性', method: '函数/方法' } as Record<string, string>)[kind] ?? kind
}
function callerName(callerId: string) {
  return codeSymbolsById.value.get(callerId)?.qualified_name ?? '未知调用方'
}
function calleeName(call: JavaCodeStructure['calls'][number]) {
  const calleeId = call.callee_ids.length === 1 ? call.callee_ids[0] : undefined
  return calleeId ? codeSymbolsById.value.get(calleeId)?.qualified_name ?? call.callee_name : call.callee_name
}
function typeRelationshipLabel(kind: JavaCodeStructure['type_relationships'][number]['kind']) {
  return kind === 'extends' ? '继承' : '实现'
}
function relatedTypeName(relationship: JavaCodeStructure['type_relationships'][number]) {
  const targetId = relationship.target_ids.length === 1 ? relationship.target_ids[0] : undefined
  return targetId ? relatedTypesById.value.get(targetId)?.qualified_name ?? relationship.target_name : relationship.target_name
}
function relatedTypeLocations(relationship: JavaCodeStructure['type_relationships'][number]) {
  return relationship.target_ids
    .map(id => relatedTypesById.value.get(id))
    .filter((item): item is JavaCodeStructure['related_types'][number] => Boolean(item))
    .map(item => `${item.source_path} · 第 ${item.start_line}–${item.end_line} 行`)
    .join('；')
}
function relatedMethodName(call: JavaCodeStructure['cross_file_calls'][number]) {
  const targetId = call.target_ids.length === 1 ? call.target_ids[0] : undefined
  return targetId ? relatedMethodsById.value.get(targetId)?.qualified_name ?? call.callee_name : call.callee_name
}
function relatedMethodLocations(call: JavaCodeStructure['cross_file_calls'][number]) {
  return call.target_ids
    .map(id => relatedMethodsById.value.get(id))
    .filter((item): item is JavaCodeStructure['related_methods'][number] => Boolean(item))
    .map(item => `${item.source_path} · 第 ${item.start_line}–${item.end_line} 行`)
    .join('；')
}
function agentTargetName(call: AgentCallAnalysis['calls'][number]) {
  if (!call.target_ids.length) return '未解析目标'
  return call.target_ids
    .map(id => agentTargetsById.value.get(id)?.qualified_name ?? '未知候选')
    .join(' / ')
}
function agentTargetLocations(call: AgentCallAnalysis['calls'][number]) {
  return call.target_ids
    .map(id => agentTargetsById.value.get(id))
    .filter((item): item is AgentCallAnalysis['related_symbols'][number] => Boolean(item))
    .map(item => `${item.source_path} · 第 ${item.start_line}–${item.end_line} 行`)
    .join('；')
}

function sourceName(source: SourceListItem | ApiSource) {
  return source.relative_path || source.original_name
}
function sourceMeta(source: SourceListItem | ApiSource) {
  const repository = source.repository_name ? `仓库 · ${source.repository_name} · ` : ''
  return `${repository}${formatSize(source.size_bytes)}`
}
</script>

<template>
  <main class="source-workspace" aria-labelledby="source-workspace-title">
    <header class="source-page-heading">
      <div>
        <h1 id="source-workspace-title">{{ view === 'projects' ? '我的项目' : '资料来源' }}</h1>
        <p>把技术笔记和源码留在项目里，让每段证据都有迹可循。</p>
      </div>
      <span class="data-label">真实项目与资料</span>
    </header>

    <div class="source-layout">
      <aside class="project-column" aria-label="项目管理">
        <div class="source-section-heading">
          <h2>选择项目</h2>
          <button class="text-button" type="button" :disabled="loading.projects || loading.create || locked" @click="emit('projectsPage', projects?.page ?? 1)">刷新项目</button>
        </div>
        <p v-if="loading.projects" role="status" class="muted-copy">正在读取项目…</p>
        <div v-if="errors.projects" class="inline-error" role="alert">
          <p>{{ errors.projects }}</p>
          <button type="button" class="text-button" @click="emit('projectsPage', projects?.page ?? 1)">重试加载项目</button>
        </div>
        <p v-if="!loading.projects && !errors.projects && projects?.total === 0" class="empty-copy">还没有项目。先给这组笔记起一个名字。</p>
        <div class="project-list">
          <button v-for="item in projects?.items ?? []" :key="item.id" class="project-choice" type="button"
            :aria-pressed="project?.id === item.id" :class="{ selected: project?.id === item.id }"
            :disabled="locked || loading.create" @click="emit('selectProject', item)">
            <span class="project-symbol" aria-hidden="true">◇</span>
            <span><strong>{{ item.name }}</strong><small>{{ item.description || '暂无项目说明' }}</small></span>
          </button>
        </div>
        <nav v-if="projectPages > 1" class="source-pagination" aria-label="项目分页">
          <button type="button" :disabled="loading.projects || locked || (projects?.page ?? 1) <= 1" @click="emit('projectsPage', (projects?.page ?? 1) - 1)">上一页</button>
          <span>{{ projects?.page }} / {{ projectPages }}</span>
          <button type="button" :disabled="loading.projects || locked || (projects?.page ?? 1) >= projectPages" @click="emit('projectsPage', (projects?.page ?? 1) + 1)">下一页</button>
        </nav>

        <details class="project-create" :open="view === 'projects' || projects?.total === 0">
          <summary>新建项目</summary>
          <form class="project-form" @submit.prevent="submitProject">
          <label for="project-name">项目名称</label>
          <input id="project-name" v-model="name" name="project-name" required maxlength="120" placeholder="例如：订单一致性研究" :disabled="loading.create || locked" />
          <label for="project-description">项目说明 <span>选填</span></label>
          <textarea id="project-description" v-model="description" maxlength="4000" rows="3" placeholder="记录这组笔记的主题与背景" :disabled="loading.create || locked" />
          <p v-if="errors.create" role="alert" class="inline-error">{{ errors.create }}</p>
          <button class="primary-button" type="submit" :disabled="loading.create || locked || !name.trim()">{{ loading.create ? '正在创建…' : '创建项目' }}</button>
          </form>
        </details>
      </aside>

      <section class="source-column" aria-label="项目资料">
        <slot name="evidence-navigation" />
        <div v-if="!project" class="source-empty-state">
          <span class="empty-source-mark" aria-hidden="true">⌑</span>
          <h2>从一篇笔记开始</h2>
          <p>选择或创建项目，然后上传 {{ sourceLanguageHint }} 文件。解析后可以查看结构和对应行号。</p>
        </div>
        <template v-else>
          <header class="source-project-heading">
            <div><h2>{{ project.name }}</h2><p>{{ project.description || '在这里保存项目的技术笔记。' }}</p></div>
            <div class="upload-control">
              <button class="text-button" type="button" :disabled="locked" @click="emit('graph')">查看项目图谱</button>
              <input ref="singleFileInput" class="file-picker" type="file" :accept="sourceFileAccept" aria-label="选择一个 Markdown 或代码文件" tabindex="-1" :disabled="locked" @change="chooseSingleFile" />
              <button class="primary-button" type="button" :disabled="locked" @click="singleFileInput?.click()">{{ loading.upload && uploadKind === 'file' ? '正在上传…' : '上传单个文件' }}</button>
              <input ref="folderInput" class="file-picker" type="file" aria-label="选择包含 Markdown 或代码文件的文件夹" tabindex="-1" :disabled="locked" webkitdirectory directory multiple @change="chooseFolder" />
              <button class="primary-button" type="button" :disabled="locked" @click="folderInput?.click()">{{ loading.upload && uploadKind === 'folder' ? '正在上传文件夹…' : '上传文件夹' }}</button>
            </div>
          </header>
          <p class="source-upload-hint">支持 UTF-8 {{ sourceLanguageHint }} 文件。文件夹最多导入 50 份支持文件，保存仓库与相对路径；其他类型与空文件会被忽略。</p>
          <p v-if="selectionNote" class="muted-copy" role="status">{{ selectionNote }}</p>
          <p v-if="notice" class="success-copy" role="status">{{ notice }}</p>
          <p v-if="fileError || errors.upload" class="inline-error" role="alert">{{ fileError || errors.upload }}</p>

          <section class="repository-panel" aria-labelledby="repository-panel-title">
            <div class="source-section-heading">
              <h3 id="repository-panel-title">来源仓库 <span v-if="repositories">{{ repositories.total }}</span></h3>
              <button class="text-button" type="button" :disabled="loading.repositories || locked" @click="emit('repositoriesPage', repositories?.page ?? 1)">刷新仓库</button>
            </div>
            <p v-if="loading.repositories" class="muted-copy" role="status">正在读取仓库身份…</p>
            <div v-if="errors.repositories" class="inline-error" role="alert"><p>{{ errors.repositories }}</p><button class="text-button" type="button" @click="emit('repositoriesPage', repositories?.page ?? 1)">重试加载仓库</button></div>
            <p v-if="errors.sync" class="inline-error" role="alert">{{ errors.sync }}</p>
            <p v-if="errors.activity" class="inline-error" role="alert">{{ errors.activity }}</p>
            <p v-if="errors.commit" class="inline-error" role="alert">{{ errors.commit }}</p>
            <p v-if="!loading.repositories && !errors.repositories && repositories?.total === 0" class="empty-copy">尚未登记仓库；上传文件夹或登记 GitHub 地址后会显示在这里。</p>
            <div v-if="repositories?.items.length" class="repository-list">
              <article v-for="repository in repositories.items" :key="repository.id" class="repository-card">
                <span>{{ repository.kind === 'local_folder' ? '本地文件夹' : 'GitHub 远程仓库' }}</span>
                <strong>{{ repository.name }}</strong>
                <a v-if="repository.remote_url" :href="repository.remote_url" target="_blank" rel="noopener noreferrer">{{ repository.remote_url }}</a>
                <small v-else>尚未关联 GitHub remote</small>
                <small v-if="repository.provider_repository_id">GitHub ID · {{ repository.provider_repository_id }}</small>
                <div v-if="repository.provider === 'github'" class="repository-sync">
                  <label :for="`github-ref-${repository.id}`">同步 ref <span>选填</span></label>
                  <input :id="`github-ref-${repository.id}`" v-model="githubRefs[repository.id]" type="text" maxlength="255" placeholder="默认分支" :disabled="locked" />
                  <label><input v-model="githubRescans[repository.id]" type="checkbox" :disabled="locked" />重新扫描（发现新增语言文件）</label>
                  <button class="text-button" type="button" :disabled="locked" @click="emit('syncGithub', { repositoryId: repository.id, ref: githubRefs[repository.id]?.trim() || undefined, rescan: githubRescans[repository.id] ?? false })">{{ loading.sync ? '正在同步…' : '同步 GitHub 内容' }}</button>
                  <button class="text-button" type="button" :disabled="locked" @click="emit('importGithubActivity', repository.id)">{{ loading.activity ? '正在导入…' : '导入 Issue / PR / Review thread' }}</button>
                  <button class="text-button" type="button" :disabled="locked" @click="emit('snapshots', repository)">查看同步快照</button>
                </div>
              </article>
            </div>
            <nav v-if="repositoryPages > 1" class="source-pagination" aria-label="仓库分页">
              <button type="button" :disabled="loading.repositories || locked || (repositories?.page ?? 1) <= 1" @click="emit('repositoriesPage', (repositories?.page ?? 1) - 1)">上一页</button>
              <span>{{ repositories?.page }} / {{ repositoryPages }}</span>
              <button type="button" :disabled="loading.repositories || locked || (repositories?.page ?? 1) >= repositoryPages" @click="emit('repositoriesPage', (repositories?.page ?? 1) + 1)">下一页</button>
            </nav>
            <slot name="snapshots" />
            <details class="repository-register">
              <summary>登记 GitHub remote</summary>
              <form class="repository-form" @submit.prevent="submitGithubRepository">
                <label for="github-remote-url">GitHub 仓库地址</label>
                <input id="github-remote-url" v-model="remoteUrl" type="text" maxlength="1024" required placeholder="https://github.com/owner/repository" :disabled="locked" />
                <label for="local-repository-link">关联本地仓库 <span>选填</span></label>
                <select id="local-repository-link" v-model="localRepositoryId" :disabled="locked || !linkableLocalRepositories.length">
                  <option value="">不关联，登记为远程仓库</option>
                  <option v-for="repository in linkableLocalRepositories" :key="repository.id" :value="repository.id">{{ repository.name }}</option>
                </select>
                <p class="source-upload-hint">接受 GitHub HTTPS 或 SSH remote；登记后可显式同步默认分支或指定 ref 中最多 50 份支持的 Markdown/多语言代码文件。</p>
                <p v-if="errors.remote" class="inline-error" role="alert">{{ errors.remote }}</p>
                <button class="primary-button" type="submit" :disabled="locked || !remoteUrl.trim()">{{ loading.remote ? '正在登记…' : '登记 remote' }}</button>
              </form>
            </details>
          </section>

          <slot name="code-search" />
          <div class="source-section-heading">
            <h3>项目资料 <span v-if="sources">{{ sources.total }}</span></h3>
            <button class="text-button" type="button" :disabled="loading.sources || locked" @click="emit('sourcesPage', sources?.page ?? 1)">刷新资料</button>
          </div>
          <p v-if="loading.sources" class="muted-copy" role="status">正在读取资料…</p>
          <div v-if="errors.sources" class="inline-error" role="alert"><p>{{ errors.sources }}</p><button class="text-button" type="button" @click="emit('sourcesPage', sources?.page ?? 1)">重试加载资料</button></div>
          <p v-if="!loading.sources && !errors.sources && sources?.total === 0" class="empty-copy">这个项目还没有资料，上传第一篇笔记开始整理。</p>
          <div class="source-list">
            <button v-for="item in sources?.items ?? []" :key="item.id" class="source-row" type="button"
              :class="{ selected: selectedSourceId === item.id }" :aria-pressed="selectedSourceId === item.id"
              :disabled="locked" @click="emit('selectSource', item.id, item.task_id)">
              <span class="source-file-type" aria-hidden="true">{{ sourceTypeLabel(item.source_type) }}</span>
              <span class="source-file-name"><strong>{{ sourceName(item) }}</strong><small>{{ sourceMeta(item) }}</small></span>
              <span class="source-status" :class="`status-${item.task_status ?? item.status}`">{{ statusLabels[item.task_status ?? item.status] }}</span>
            </button>
          </div>
          <nav v-if="sourcePages > 1" class="source-pagination" aria-label="资料分页">
            <button type="button" :disabled="loading.sources || locked || (sources?.page ?? 1) <= 1" @click="emit('sourcesPage', (sources?.page ?? 1) - 1)">上一页</button>
            <span>{{ sources?.page }} / {{ sourcePages }}</span>
            <button type="button" :disabled="loading.sources || locked || (sources?.page ?? 1) >= sourcePages" @click="emit('sourcesPage', (sources?.page ?? 1) + 1)">下一页</button>
          </nav>

          <section v-if="selectedSourceId" id="source-reader" class="source-reader" tabindex="-1" aria-label="原文与解析结果" :aria-busy="loading.detail || loading.task || loading.chunks || loading.structure || loading.agent">
            <div class="source-section-heading reader-heading">
              <div><h3>{{ source ? sourceName(source) : '资料详情' }}</h3><p v-if="source" class="muted-copy">{{ source.repository_name ? `仓库 · ${source.repository_name} · ` : '' }}{{ source.line_count }} 行原文 · {{ formatSize(source.size_bytes) }}</p><a v-if="source?.git_url" class="source-git-link" :href="source.git_url" target="_blank" rel="noopener noreferrer">在 GitHub 查看来源 ↗</a></div>
              <button class="text-button" type="button" :disabled="loading.detail || locked || loading.chunks" @click="emit('refresh')">刷新状态</button>
            </div>
            <p v-if="loading.detail" role="status" class="muted-copy">正在读取原文与任务…</p>
            <p v-if="errors.detail" role="alert" class="inline-error">{{ errors.detail }} 请刷新状态重试。</p>
            <template v-if="source && !loading.detail && !errors.detail">
              <div class="task-strip" role="status">
                <span class="source-status" :class="`status-${task?.status ?? source.status}`">{{ statusLabels[task?.status ?? source.status] }}</span>
                <span v-if="loading.task">正在解析，请稍候…</span>
                <span v-else-if="source.status === 'ready'">解析完成，可以核对下方原文分块。</span>
                <span v-else-if="task?.status === 'running'">任务正在执行，刷新状态查看结果。</span>
                <span v-else-if="task?.status === 'failed'">解析未完成，可以重新尝试。</span>
                <span v-else-if="task?.status === 'cancelled'">此任务已取消。</span>
                <span v-else-if="!task">此资料没有可执行任务。</span>
                <span v-else>保留原文结构，提取可定位的段落。</span>
                <button v-if="task && ['queued', 'failed'].includes(task.status)" type="button" class="primary-button" :disabled="locked" @click="emit('run')">{{ loading.task ? '正在解析…' : task.status === 'failed' ? '重试解析' : '开始解析' }}</button>
              </div>
              <p v-if="errors.task" class="inline-error" role="alert">{{ errors.task }}</p>
              <details v-if="source.status !== 'ready'" class="raw-preview" open><summary>原文预览（最多 4000 字符）</summary><pre>{{ source.content_preview }}</pre></details>
              <template v-else>
                <section v-if="isCodeSource(source.source_type)" class="code-structure" aria-labelledby="code-structure-title">
                  <div class="source-section-heading">
                    <h3 id="code-structure-title">源码结构</h3>
                    <span v-if="codeStructure" class="muted-copy">{{ codeStructure.symbols.length }} 个符号 · {{ codeStructure.calls.length }} 条同文件调用 · {{ codeStructure.cross_file_calls.length }} 条跨文件调用 · {{ codeStructure.type_relationships.length }} 条跨文件类型关系</span>
                    <label class="agent-strategy">分析方式
                      <select v-model="agentStrategy" :disabled="locked" aria-label="跨文件调用分析方式">
                        <option value="single_step">单轮候选判断</option>
                        <option value="tools">工具调用 Agent</option>
                      </select>
                    </label>
                    <button type="button" class="primary-button" :disabled="locked || loading.structure" @click="emit('analyzeCalls', agentStrategy)">{{ loading.agent ? 'Agent 分析中…' : 'Agent 分析跨文件调用' }}</button>
                  </div>
                  <p class="source-upload-hint">结构关系由本地规则推导，不会自动写入已审核的正式知识图谱。</p>
                  <p v-if="source.source_type !== 'java'" class="source-upload-hint">{{ sourceTypeLabel(source.source_type) }} 默认只做语法结构解析；显式运行 Agent 后，才会在同仓库静态候选中分析跨文件调用并产生模型费用。</p>
                  <p v-else class="source-upload-hint">Java 保留本地确定性调用提示；显式运行 Agent 可对已有仓库内候选进一步消歧。</p>
                  <p v-if="loading.structure" class="muted-copy" role="status">正在读取源码结构…</p>
                  <p v-else-if="errors.structure" class="inline-error" role="alert">{{ errors.structure }} 请刷新状态重试。</p>
                  <template v-else-if="codeStructure">
                    <p v-if="codeStructure.truncated" class="inline-error">文件结构较大，当前仅展示有界结果。</p>
                    <p v-if="codeStructure.has_syntax_errors" class="inline-error" role="status">源码包含语法错误或不支持的语法，符号可能不完整；原文与行号仍保留。</p>
                    <div v-if="codeStructure.symbols.length" class="code-symbol-grid">
                      <article v-for="symbol in codeStructure.symbols" :key="symbol.id" class="code-symbol-card">
                        <span>{{ codeSymbolKindLabel(symbol.kind) }}</span>
                        <strong>{{ symbol.qualified_name }}</strong>
                        <small>第 {{ symbol.start_line }}–{{ symbol.end_line }} 行</small>
                      </article>
                    </div>
                    <p v-else class="empty-copy">没有识别到可展示的代码符号。</p>
                    <div v-if="codeStructure.calls.length" class="code-call-list">
                      <h4>同文件方法调用</h4>
                      <p v-for="call in codeStructure.calls" :key="call.id">
                        <strong>{{ callerName(call.caller_id) }}</strong>
                        <span aria-hidden="true">→</span>
                        <strong>{{ calleeName(call) }}</strong>
                        <small>第 {{ call.line }} 行<span v-if="call.resolution === 'ambiguous'"> · {{ call.callee_ids.length }} 个同名候选</span></small>
                      </p>
                    </div>
                    <div v-if="codeStructure.type_relationships.length" class="code-call-list code-type-relations">
                      <h4>跨文件类型关系</h4>
                      <p v-for="relationship in codeStructure.type_relationships" :key="relationship.id">
                        <strong>{{ codeSymbolsById.get(relationship.source_symbol_id)?.qualified_name ?? '未知类型' }}</strong>
                        <span>{{ typeRelationshipLabel(relationship.kind) }}</span>
                        <strong>{{ relatedTypeName(relationship) }}</strong>
                        <small>声明第 {{ relationship.line }} 行 · {{ relatedTypeLocations(relationship) }}<span v-if="relationship.resolution === 'ambiguous'"> · {{ relationship.target_ids.length }} 个同名候选</span></small>
                      </p>
                    </div>
                    <div v-if="codeStructure.cross_file_calls.length" class="code-call-list code-cross-file-calls">
                      <h4>跨文件方法调用</h4>
                      <p v-for="call in codeStructure.cross_file_calls" :key="call.id">
                        <strong>{{ callerName(call.caller_id) }}</strong>
                        <span aria-hidden="true">→</span>
                        <strong>{{ relatedMethodName(call) }}</strong>
                        <small>调用第 {{ call.line }} 行 · 接收者 {{ call.receiver }} · {{ relatedMethodLocations(call) }}<span v-if="call.resolution === 'ambiguous'"> · {{ call.target_ids.length }} 个同名候选</span></small>
                      </p>
                    </div>
                    <section class="agent-call-analysis" aria-labelledby="agent-call-analysis-title" :aria-busy="loading.agent">
                      <div class="source-section-heading">
                        <h4 id="agent-call-analysis-title">Agent 跨文件分析</h4>
                        <span v-if="agentCallAnalysis" class="muted-copy">扫描 {{ agentCallAnalysis.scanned_source_count }} 个文件 · {{ agentCallAnalysis.candidate_call_count }} 个候选调用 · {{ agentCallAnalysis.provider_call_count }} 次模型调用 · {{ agentCallAnalysis.tool_call_count }} 次工具调用</span>
                      </div>
                      <p v-if="loading.agent" class="muted-copy" role="status">Agent 正在核对导入、接收者、文件路径和候选声明…</p>
                      <p v-else-if="errors.agent" class="inline-error" role="alert">{{ errors.agent }} <button type="button" class="text-button" @click="emit('analyzeCalls', agentStrategy)">重试分析</button></p>
                      <template v-else-if="agentCallAnalysis">
                        <details v-if="agentCallAnalysis.tool_trace?.length" class="agent-tool-trace"><summary>查看工具执行记录</summary><ol><li v-for="(entry, index) in agentCallAnalysis.tool_trace" :key="index">{{ entry.name }} · {{ entry.status === 'ok' ? '成功' : '参数或范围被拒绝' }} · {{ entry.duration_ms }} ms</li></ol></details>
                        <p v-if="agentCallAnalysis.truncated" class="inline-error">仓库或候选达到分析上限，结果可能不完整。</p>
                        <p v-if="agentCallAnalysis.has_syntax_errors" class="inline-error">扫描范围中存在语法错误，Agent 结果仅作为有界提示。</p>
                        <p v-if="!agentCallAnalysis.calls.length" class="empty-copy">没有找到可交给 Agent 判断的同仓库跨文件候选；本次未调用模型。</p>
                        <div v-else class="code-call-list code-agent-calls">
                          <p v-for="call in agentCallAnalysis.calls" :key="call.id">
                            <strong>{{ call.caller_id ? callerName(call.caller_id) : '文件顶层' }}</strong>
                            <span aria-hidden="true">→</span>
                            <strong>{{ agentTargetName(call) }}</strong>
                            <small>调用第 {{ call.line }} 行 · {{ call.resolution }} · 置信度 {{ Math.round(call.confidence * 100) }}%<span v-if="agentTargetLocations(call)"> · {{ agentTargetLocations(call) }}</span></small>
                            <small>{{ call.resolution_basis }}</small>
                            <code>{{ call.call_quote }}</code>
                          </p>
                        </div>
                      </template>
                    </section>
                  </template>
                </section>
                <div class="source-section-heading"><h3>原文分块 <span v-if="chunks">{{ chunks.total }}</span></h3><span class="muted-copy">行号对应上传原文</span></div>
                <p class="source-upload-hint">分块保留原文与行号；下方可提取有原文证据的候选知识。</p>
                <p v-if="loading.chunks" role="status" class="muted-copy">正在读取分块…</p>
                <p v-if="errors.chunks" role="alert" class="inline-error">{{ errors.chunks }} <button class="text-button" type="button" @click="emit('chunksPage', chunks?.page ?? 1)">重试加载分块</button></p>
                <p v-if="!loading.chunks && !errors.chunks && chunks?.total === 0" class="empty-copy">解析已完成，没有可展示的内容块。</p>
                <div v-if="!loading.chunks && !errors.chunks" class="chunk-list">
                  <article v-for="chunk in chunks?.items ?? []" :key="chunk.id" :id="`source-chunk-${chunk.id}`" class="source-chunk" :class="{ 'focused-code-chunk': focusedChunkId === chunk.id }" tabindex="-1">
                    <header><span>{{ kindLabels[chunk.kind] }} <strong>第 {{ chunk.start_line }}–{{ chunk.end_line }} 行</strong></span><span>{{ chunk.heading_path.join(' / ') || '文档开头' }}</span></header>
                    <pre role="group" tabindex="0" :aria-label="`原文第 ${chunk.start_line} 至 ${chunk.end_line} 行`">{{ chunk.content }}</pre>
                  </article>
                </div>
                <nav v-if="chunkPages > 1" class="source-pagination" aria-label="分块分页">
                  <button type="button" :disabled="loading.chunks || (chunks?.page ?? 1) <= 1" @click="emit('chunksPage', (chunks?.page ?? 1) - 1)">上一页</button>
                  <span>{{ chunks?.page }} / {{ chunkPages }}</span>
                  <button type="button" :disabled="loading.chunks || (chunks?.page ?? 1) >= chunkPages" @click="emit('chunksPage', (chunks?.page ?? 1) + 1)">下一页</button>
                </nav>
                <slot name="reviews" />
              </template>
            </template>
          </section>
        </template>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RepositorySnapshotList, SourceRepository } from '../api/knowledgeAtlas'

const props = defineProps<{
  repository: SourceRepository | null
  snapshots: RepositorySnapshotList | null
  loading: boolean
  error: string
  requestedPage: number
  importingId: string
  locked: boolean
}>()
const emit = defineEmits<{
  page: [page: number]
  import: [snapshotId: string]
  close: []
}>()
const pages = computed(() => Math.max(1, Math.ceil((props.snapshots?.total ?? 0) / (props.snapshots?.page_size ?? 10))))
function commitUrl(sha: string) {
  return props.repository?.remote_url ? `${props.repository.remote_url}/commit/${encodeURIComponent(sha)}` : ''
}
</script>

<template>
  <section v-if="repository" class="snapshot-history" aria-labelledby="snapshot-history-title" :aria-busy="loading || Boolean(importingId)">
    <div class="source-section-heading"><h3 id="snapshot-history-title">同步快照 · {{ repository.name }}</h3><button class="text-button" type="button" :disabled="locked" @click="emit('close')">关闭快照历史</button></div>
    <p class="source-upload-hint">这里只展示已保存的同步记录，不读取 GitHub。可把提交说明加入资料，再解析、抽取并审核；资料不包含代码 diff，也不证明提交说明中的结论成立。</p>
    <p v-if="loading" class="muted-copy" role="status">正在读取快照历史…</p>
    <div v-else-if="error" class="inline-error" role="alert"><p>{{ error }}</p><button class="text-button" type="button" :disabled="locked" @click="emit('page', requestedPage)">重试快照历史</button></div>
    <template v-else-if="snapshots">
      <p v-if="!snapshots.items.length" class="empty-copy">尚无同步快照。先在仓库卡片中同步 GitHub 内容。</p>
      <div v-else class="snapshot-history-list">
        <article v-for="item in snapshots.items" :key="item.id" class="snapshot-row">
          <div><strong>{{ item.commit_sha.slice(0, 12) }} · {{ item.ref }}</strong><small>同步记录：{{ new Date(item.created_at).toLocaleString() }} · {{ item.file_count }} 份入选文件</small></div>
          <p class="snapshot-message" role="group" aria-label="提交说明" tabindex="0">{{ item.commit_message || '没有保存提交说明' }}</p>
          <small v-if="item.truncated" class="snapshot-warning">此快照的文件集合或下载预算受限，不能代表完整仓库。</small>
          <div class="snapshot-actions"><a v-if="repository.remote_url" :href="commitUrl(item.commit_sha)" target="_blank" rel="noopener noreferrer">在 GitHub 查看提交 ↗</a><button class="text-button" type="button" :disabled="locked" @click="emit('import', item.id)">{{ importingId === item.id ? '正在保存…' : item.commit_source_id ? '打开提交资料' : '将提交说明加入资料' }}</button></div>
        </article>
      </div>
      <nav v-if="pages > 1" class="source-pagination" aria-label="快照历史分页"><button type="button" :disabled="locked || loading || snapshots.page <= 1" @click="emit('page', snapshots.page - 1)">上一页</button><span>{{ snapshots.page }} / {{ pages }}</span><button type="button" :disabled="locked || loading || snapshots.page >= pages" @click="emit('page', snapshots.page + 1)">下一页</button></nav>
    </template>
  </section>
</template>

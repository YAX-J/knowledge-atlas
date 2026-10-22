<script setup lang="ts">
import { computed } from 'vue'
import type { RepositorySnapshotFile, RepositorySnapshotFileList } from '../api/knowledgeAtlas'

const props = defineProps<{
  snapshotId: string
  files: RepositorySnapshotFileList | null
  loading: boolean
  error: string
  requestedPage: number
  locked: boolean
}>()
const emit = defineEmits<{ page: [page: number]; close: []; open: [file: RepositorySnapshotFile] }>()
const pages = computed(() => Math.max(1, Math.ceil((props.files?.total ?? 0) / (props.files?.page_size ?? 20))))
const statusLabels: Record<RepositorySnapshotFile['status'], string> = {
  imported: '已导入', reused: '已复用', unchanged: '未变化', renamed: '已改名', deleted: '远端已删除', skipped: '已跳过',
}
const sourceStatusLabels: Record<string, string> = { uploaded: '待解析', processing: '解析中', ready: '已解析', failed: '解析失败' }
</script>

<template>
  <section v-if="snapshotId" id="snapshot-files-panel" class="snapshot-files" aria-labelledby="snapshot-files-title" :aria-busy="loading" tabindex="-1">
    <div class="source-section-heading"><h4 id="snapshot-files-title">快照文件记录<span v-if="files"> · {{ files.commit_sha.slice(0, 12) }} · {{ files.total }} 项</span></h4><button type="button" class="text-button" :disabled="locked" @click="emit('close')">关闭文件记录</button></div>
    <p class="source-upload-hint">仅列出本次已保存的支持文件与删除记录，不是 Git diff，也不是完整仓库文件列表。资料可能复用于多个快照，此处文件外链固定到所选提交；打开原文不重新下载 GitHub。</p>
    <p v-if="loading" role="status">正在读取快照文件…</p>
    <div v-else-if="error" class="inline-error" role="alert"><p>{{ error }}</p><button type="button" class="text-button" :disabled="locked" @click="emit('page', requestedPage)">重试文件记录</button></div>
    <template v-else-if="files">
      <p v-if="files.truncated || !files.deletion_detection_complete" class="snapshot-warning">此快照未完整覆盖文件集合或下载预算，不能据此断言其他文件不存在或已删除。</p>
      <p v-if="!files.items.length" class="empty-copy">此页没有保存的文件记录。</p>
      <div v-else class="snapshot-file-list" role="group" aria-label="快照文件列表" tabindex="0">
        <article v-for="item in files.items" :key="item.id" class="snapshot-file-row">
          <div><strong>{{ item.path }}</strong><span class="snapshot-file-state">{{ statusLabels[item.status] }}</span></div>
          <small v-if="item.previous_path">原路径：{{ item.previous_path }}</small>
          <small>blob {{ item.blob_sha.slice(0, 12) }} · {{ item.size_bytes }} B<span v-if="item.source_status"> · {{ sourceStatusLabels[item.source_status] ?? item.source_status }}</span></small>
          <small v-if="item.error_code">跳过原因：{{ item.error_code }}</small>
          <div class="snapshot-actions">
            <button v-if="item.source_id" type="button" class="text-button" :disabled="locked" @click="emit('open', item)">{{ item.status === 'deleted' ? '打开保留资料' : '打开原文资料' }}</button><span v-else class="muted-copy">未保存可打开的资料</span>
            <a v-if="item.git_url" :href="item.git_url" target="_blank" rel="noopener noreferrer">在此提交查看文件 ↗</a>
          </div>
        </article>
      </div>
      <nav v-if="pages > 1" class="source-pagination" aria-label="快照文件分页"><button type="button" :disabled="locked || files.page <= 1" @click="emit('page', files.page - 1)">上一页</button><span>{{ files.page }} / {{ pages }}</span><button type="button" :disabled="locked || files.page >= pages" @click="emit('page', files.page + 1)">下一页</button></nav>
    </template>
  </section>
</template>

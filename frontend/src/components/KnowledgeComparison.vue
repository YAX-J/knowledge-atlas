<script setup lang="ts">
import type { EntityDetail, EvidenceLocator } from '../types'

defineProps<{ details: EntityDetail[] | null; loading: boolean; error: string; busy: boolean }>()
const emit = defineEmits<{ close: []; retry: []; openEvidence: [locator: EvidenceLocator] }>()
</script>

<template>
  <section v-if="loading || error || details" id="knowledge-comparison" class="knowledge-comparison" tabindex="-1" aria-label="并排核对知识与证据" :aria-busy="loading">
    <header><h3>并排核对知识与证据</h3><button type="button" @click="emit('close')">关闭核对</button></header>
    <p>比较名称、摘要和各自原文后再作判断；这项操作只读取知识。</p>
    <p v-if="loading" role="status">正在读取两条知识的正式证据…</p>
    <div v-else-if="error" role="alert"><p>{{ error }}</p><button type="button" :disabled="busy" @click="emit('retry')">重试核对</button></div>
    <div v-else class="comparison-columns">
      <article v-for="(detail, index) in details ?? []" :key="detail.entity.id">
        <small>知识 {{ index + 1 }} · {{ detail.entity.type }}</small>
        <h4>{{ detail.entity.name }}</h4><p>{{ detail.entity.summary }}</p>
        <div class="comparison-evidence" role="region" :aria-label="`知识 ${index + 1} 的原文证据`" tabindex="0">
          <p v-if="!detail.evidence.length">暂无可访问的原文证据。</p>
          <blockquote v-for="evidence in detail.evidence" :key="evidence.id">
            <strong>{{ evidence.title }}</strong><small>第 {{ evidence.start_line }}–{{ evidence.end_line }} 行</small>
            <p>{{ evidence.quote }}</p>
            <button type="button" :disabled="busy" @click="emit('openEvidence', evidence)">核对原文分块</button>
            <a v-if="evidence.git_url" :href="evidence.git_url" target="_blank" rel="noopener noreferrer">GitHub 原文 ↗</a>
          </blockquote>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.knowledge-comparison { padding: 16px; margin: 16px 0; border: 1px solid var(--line); border-radius: 6px; background: #edf5f3; overflow-wrap: anywhere; }
header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }h3 { margin: 0; font-size: 15px; }h4 { margin: 10px 0; font-size: 16px; }
p, small { color: #435e64; font-size: 12px; line-height: 1.8; white-space: pre-wrap; }
.comparison-columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }.comparison-columns > article { min-width: 0; }
.comparison-evidence { max-height: 340px; overflow: auto; padding-right: 6px; }
blockquote { margin: 12px 0; padding: 12px; border-left: 2px solid var(--teal); background: var(--paper); font-size: 12px; }blockquote strong, blockquote small { display: block; }
button { min-height: 40px; padding: 8px 10px; border: 1px solid #aabec0; border-radius: 5px; background: var(--paper); color: var(--ink); cursor: pointer; font-size: 12px; }button:disabled { opacity: .5; cursor: not-allowed; }a { color: var(--teal); font-size: 12px; margin-left: 10px; }
:focus-visible { outline: 2px solid var(--rose); outline-offset: 3px; }
@media (max-width: 900px) { .comparison-columns { grid-template-columns: minmax(0, 1fr); } }
</style>

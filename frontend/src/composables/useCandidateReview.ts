import { computed, nextTick, onScopeDispose, ref, watch, type Ref } from 'vue'
import { extractKnowledge, getExtraction, listCandidates, resolveCandidate, resolveCandidatesBatch } from '../api/knowledgeAtlas'
import type { ApiProject, CandidateList, ExtractionResult } from '../api/knowledgeAtlas'
import type { ReviewDecision, ReviewFilters } from '../types'

export function useCandidateReview(project: Ref<ApiProject | null>, selectedSourceId: Ref<string>,
  clearIndexStatus: () => void, errorMessage: (error: unknown) => string) {
  let reviewsRequest = 0
  let reviewAction = 0
  let disposed = false
  const candidates = ref<CandidateList | null>(null)
  const reviewFilters = ref<ReviewFilters>({ status: '', kind: '', query: '' })
  const extraction = ref<ExtractionResult | null>(null)
  const reviewsLoading = ref(false)
  const extracting = ref(false)
  const resolving = ref('')
  const reviewBusy = computed(() => extracting.value || Boolean(resolving.value))
  const reviewsError = ref('')
  const reviewsNotice = ref('')
  function clearReviews() {
    reviewsRequest++; reviewAction++
    candidates.value = null
    reviewFilters.value = { status: '', kind: '', query: '' }
    extraction.value = null
    reviewsLoading.value = extracting.value = false
    resolving.value = reviewsError.value = reviewsNotice.value = ''
  }
  async function applyReviewFilters(filters: ReviewFilters) {
    if (disposed || reviewBusy.value) return
    const projectId = project.value?.id
    const sourceId = selectedSourceId.value
    reviewFilters.value = { ...filters }
    const applied = reviewFilters.value
    candidates.value = null
    await loadReviews(1)
    await nextTick()
    if (project.value?.id !== projectId || selectedSourceId.value !== sourceId || reviewFilters.value !== applied) return
    const heading = document.getElementById('candidate-title')
    heading?.focus({ preventScroll: true })
    heading?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
  }

  async function loadReviews(page = candidates.value?.page ?? 1) {
    const sourceId = selectedSourceId.value
    const projectId = project.value?.id
    if (disposed || !sourceId || !projectId) return
    const request = ++reviewsRequest
    reviewsLoading.value = true
    reviewsError.value = ''
    const filters = { ...reviewFilters.value }
    try {
      const [batch, status] = await Promise.all([listCandidates(projectId, sourceId, page, filters), getExtraction(sourceId)])
      if (request !== reviewsRequest || sourceId !== selectedSourceId.value) return
      const lastPage = Math.max(1, Math.ceil(batch.total / batch.page_size))
      if (page > lastPage) { await loadReviews(lastPage); return }
      candidates.value = batch
      extraction.value = status
      if (status.task?.status === 'failed') {
        const message = status.task.error?.message
        reviewsError.value = typeof message === 'string' ? message : '提取失败，请重试。'
      }
    } catch (error) {
      if (request === reviewsRequest) reviewsError.value = errorMessage(error)
    } finally {
      if (request === reviewsRequest) reviewsLoading.value = false
    }
  }

  async function extractSource() {
    const sourceId = selectedSourceId.value
    if (disposed || !sourceId || extracting.value || resolving.value) return
    const action = ++reviewAction
    reviewsRequest++
    reviewsLoading.value = false
    extracting.value = true
    reviewsError.value = reviewsNotice.value = ''
    try {
      const result = await extractKnowledge(sourceId)
      if (action !== reviewAction || sourceId !== selectedSourceId.value) return
      extraction.value = result
      await loadReviews(1)
      if (action === reviewAction && result.task?.status === 'succeeded') reviewsNotice.value = `已生成 ${result.candidate_count} 条候选知识，请逐项核对证据。`
    } catch (error) {
      if (action === reviewAction) reviewsError.value = errorMessage(error)
    } finally {
      if (action === reviewAction) extracting.value = false
    }
  }

  async function reviewCandidate(decision: ReviewDecision) {
    if (disposed || !project.value || !selectedSourceId.value || extracting.value || resolving.value) return
    const action = ++reviewAction
    reviewsRequest++
    reviewsLoading.value = false
    resolving.value = decision.id
    reviewsError.value = reviewsNotice.value = ''
    try {
      await resolveCandidate(decision)
      if (action !== reviewAction) return
      clearIndexStatus()
      await loadReviews()
      if (action === reviewAction) reviewsNotice.value = decision.action === 'confirm' ? '知识已写入项目图谱，审核记录已保存。' : '候选知识已拒绝，审核记录已保存。'
    } catch (error) {
      if (action === reviewAction) reviewsError.value = errorMessage(error)
    } finally {
      if (action === reviewAction) resolving.value = ''
    }
  }

  async function reviewCandidatesBatch(ids: string[], decision: 'confirm' | 'reject') {
    const projectId = project.value?.id
    const sourceId = selectedSourceId.value
    if (disposed || !projectId || !sourceId || !ids.length || extracting.value || resolving.value) return
    const action = ++reviewAction
    reviewsRequest++
    reviewsLoading.value = false
    resolving.value = 'batch'
    reviewsError.value = reviewsNotice.value = ''
    try {
      const result = await resolveCandidatesBatch(projectId, sourceId, ids, decision)
      if (action !== reviewAction || project.value?.id !== projectId || selectedSourceId.value !== sourceId) return
      clearIndexStatus()
      await loadReviews()
      if (action === reviewAction) reviewsNotice.value = `已${decision === 'confirm' ? '确认' : '拒绝'} ${result.processed_count} 条候选，整批审核记录已保存。`
    } catch (error) {
      if (action === reviewAction) reviewsError.value = errorMessage(error)
    } finally {
      if (action === reviewAction) resolving.value = ''
    }
  }


  watch(() => [project.value?.id, selectedSourceId.value], clearReviews, { flush:'sync' })
  onScopeDispose(() => { disposed = true; clearReviews() })
  return { candidates, reviewFilters, extraction, reviewsLoading, extracting, resolving, reviewBusy,
    reviewsError, reviewsNotice, clearReviews, applyReviewFilters, loadReviews, extractSource, reviewCandidate, reviewCandidatesBatch }
}

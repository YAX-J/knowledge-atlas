export type NodeType =
  | 'project'
  | 'concept'
  | 'pattern'
  | 'decision'
  | 'note'
  | 'question'
  | 'code'

export interface KnowledgeNode {
  id: string
  label: string
  subtitle: string
  type: NodeType
  x: number
  y: number
  size: number
  description: string
  confidence: number
  validFrom: string
  project: string
  evidenceIds: string[]
}

export interface KnowledgeEdge {
  id: string
  source: string
  target: string
  label: string
  highlighted?: boolean
}

export interface Evidence {
  id: string
  kind: 'md' | 'java' | 'adr' | 'git'
  title: string
  location: string
  excerpt: string
  updatedAt: string
}

export interface TimelinePoint {
  value: number
  date: string
  label: string
}

export type WorkspaceNav = 'graph' | 'projectGraph' | 'projects' | 'sources' | 'questions' | 'workbench' | 'conversations' | 'agents'

export type IngestionOperation = 'projects' | 'create' | 'repositories' | 'remote' | 'sync' | 'activity' | 'commit' | 'sources' | 'upload' | 'detail' | 'task' | 'chunks' | 'structure' | 'agent'
export type IngestionLoading = Record<IngestionOperation, boolean>
export type IngestionErrors = Record<IngestionOperation, string>
export interface SourceFilters {
  query: string
  type: string
  status: '' | 'uploaded' | 'processing' | 'ready' | 'failed'
}
export interface CandidateEvidence {
  chunk_id: string
  quote: string
  start_line: number
  end_line: number
  heading_path: string[]
}

export interface KnowledgeCandidate {
  id: string
  project_id: string
  source_id: string
  task_id: string
  kind: 'entity' | 'relation'
  type: string
  name: string
  summary: string
  confidence: number
  review_status: 'pending' | 'confirmed' | 'rejected'
  knowledge_id: string | null
  evidence: CandidateEvidence[]
  source_candidate_id: string | null
  target_candidate_id: string | null
  endpoints?: { id: string; name: string; review_status: 'pending' | 'confirmed' | 'rejected' }[]
  created_at: string
  updated_at: string
}

export interface ReviewDecision {
  id: string
  action: 'confirm' | 'reject'
  changes?: { name?: string; summary?: string }
}

export interface ReviewFilters {
  status: '' | 'pending' | 'confirmed' | 'rejected'
  kind: '' | 'entity' | 'relation'
  query: string
}

export interface FormalKnowledgeNode {
  id: string
  project_id: string
  candidate_id: string
  type: string
  name: string
  summary: string
  confidence: number
  status: string
  valid_from: string
  valid_to: string | null
  evidence_count: number
}

export interface FormalKnowledgeEdge extends FormalKnowledgeNode {
  source_id: string
  target_id: string
}

export interface ProjectGraphData {
  nodes: FormalKnowledgeNode[]
  edges: FormalKnowledgeEdge[]
  truncated: boolean
}

export type KnowledgeChangeKind = 'SUPERSEDES' | 'SUPPLEMENTS' | 'CONFLICTS_WITH'
export interface KnowledgeChangeInput {
  new_entity_id: string
  old_entity_id: string
  evidence_id: string
  kind: KnowledgeChangeKind
  reason: string
  effective_at: string
}
export interface KnowledgeChange extends KnowledgeChangeInput {
  id: string
  project_id: string
  new_entity_name: string
  old_entity_name: string
  review_status: 'pending' | 'confirmed' | 'rejected'
  resolved_at: string | null
  created_at: string
  before: Record<string, unknown>
  after: Record<string, unknown>
  evidence: FormalEvidence[]
}
export interface KnowledgeChangeList {
  items: KnowledgeChange[]
  total: number
  page: number
  page_size: number
}
export interface KnowledgeHistory {
  entities: FormalKnowledgeNode[]
  changes: KnowledgeChange[]
  truncated: boolean
}
export type GovernanceKind = 'missing_evidence' | 'duplicate' | 'possible_conflict' | 'orphan'

export interface GovernanceResult {
  checked_at: string
  scanned_entity_count: number
  truncated: boolean
  kind_filter?: GovernanceKind | null
  counts_by_kind?: Partial<Record<GovernanceKind, number>>
  findings: {
    id: string
    kind: GovernanceKind
    entity_ids: string[]
    message: string
    entities?: { id: string; name: string; summary: string; type: string }[]
  }[]
}

export interface EvidenceLocator {
  source_id: string
  chunk_id: string
}

export interface FormalEvidence extends CandidateEvidence, EvidenceLocator {
  id: string
  source_id: string
  title: string
  uri: string
  git_url: string | null
}

export interface EntityDetail {
  entity: FormalKnowledgeNode
  evidence: FormalEvidence[]
  relationships: FormalKnowledgeEdge[]
  truncated: boolean
}

export interface RelationshipDetail {
  relationship: FormalKnowledgeEdge
  evidence: FormalEvidence[]
}

export type KnowledgeSearchMode = 'keyword' | 'bm25' | 'bm25_source' | 'vector' | 'hybrid' | 'rrf'
export type QuestionRetrievalMode = Exclude<KnowledgeSearchMode, 'keyword'>

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface ProjectOverview { project_id: string; sources: number; ready_sources: number; pending_reviews: number; entities: number; relationships: number; pending_tasks: number }
export interface Conversation { id: string; project_id: string; title: string; created_at: string; updated_at: string }
export interface ConversationTurn { id: string; request_id: string; position: number; question: string; retrieval_mode: QuestionRetrievalMode; valid_at: string | null; status: 'running' | 'succeeded' | 'failed' | 'interrupted'; error_code: string | null; answer: QuestionAnswer | null; created_at: string }
export interface IdentityInfo { entity_id: string; canonical_id: string; aliases: string[]; member_ids: string[] }
export interface OperationInput { action: 'alias' | 'merge' | 'unmerge' | 'withdraw' | 'reactivate' | 'reverse_change'; kind: 'entity' | 'relationship'; knowledge_id: string; target_id?: string; alias?: string; reason: string }
export interface KnowledgeOperation { id: string; action: string; reason: string; payload: Record<string, unknown>; before: Record<string, unknown>; after: Record<string, unknown>; created_at: string }
export type ManagementIntent = OperationInput | { action: 'evolution_group'; old_entity_ids: string[]; new_entity_ids: string[]; reason: string }

export interface RetirementInput {
  kind: 'entity' | 'relationship'
  knowledge_id: string
  category: 'correction' | 'obsolete'
  reason: string
}

export interface KnowledgeRetirement extends RetirementInput {
  id: string
  project_id: string
  name: string
  effective_at: string
  before: { valid_from: string; valid_to: string | null; [key: string]: unknown }
  after: { valid_from: string; valid_to: string | null; [key: string]: unknown }
}

export interface RetirementList {
  items: KnowledgeRetirement[]
  page: number
  page_size: number
  total: number
}

export interface KnowledgeSearchResult {
  query: string
  mode: KnowledgeSearchMode
  items: {
    entity: FormalKnowledgeNode
    keyword_score: number | null
    bm25_score?: number | null
    rrf_score?: number | null
    lexical_rank?: number | null
    vector_rank?: number | null
    vector_score: number | null
    keyword_component: number | null
    vector_component: number | null
    graph_score: number | null
    hybrid_score: number | null
    matched_fields: ('name' | 'summary' | 'evidence' | 'provenance')[]
    graph_connections: {
      relationship_id: string
      relationship_type: string
      relationship_name: string
      related_entity_id: string
      related_entity_name: string
      score: number
    }[]
    evidence: FormalEvidence[]
  }[]
  truncated: boolean
  indexed_count: number | null
  eligible_count: number | null
  weights: { keyword: number; vector: number; graph: number } | null
  lexical?: {
    protocol: 'mixed-bm25-v1' | 'mixed-bm25-source-v1' | 'mixed-bm25-v2' | 'mixed-bm25-source-v2'
    query_terms: string[]
    scanned_count: number
    entity_limit: number
    text_limit_per_entity: number
    batch_size?: number | null
    evidence_limit_per_entity?: number | null
    matched_count?: number | null
    results_truncated?: boolean
    truncated_reasons: ('entity_limit' | 'evidence_limit' | 'text_limit')[]
  } | null
}

export interface EmbeddingRebuildResult {
  model: string
  dimensions: number
  eligible_count: number
  updated_count: number
  reused_count: number
}

export interface EmbeddingJob {
  id: string
  project_id: string
  status: 'running' | 'succeeded' | 'failed'
  interrupted: boolean
  started_at: string
  lease_expires_at: string
  completed_at: string | null
  result: EmbeddingRebuildResult | null
  error: { code: string; message: string } | null
}

export interface EmbeddingIndexStatus {
  model: string
  dimensions: number
  configured: boolean
  checked_at: string
  eligible_count: number
  indexed_count: number
  missing_count: number
  stale_count: number
  current_count: number
  scanned_count: number
  scan_limit: number
  truncated: boolean
}

export interface QuestionEvidence extends FormalEvidence {
  entity_id: string
  entity_name: string
  related_entities?: { id: string; name: string }[]
}

export interface QuestionAnswer {
  id: string
  question: string
  supported: boolean
  answer: string
  confidence: number
  entity_ids: string[]
  evidence: QuestionEvidence[]
  retrieval: {
    mode?: QuestionRetrievalMode
    bm25_hits?: number
    unique_evidence_count?: number
    duplicate_evidence_count?: number
    truncated?: boolean
    keyword_hits: number
    vector_hits: number
    graph_hits: number
    indexed_count: number
    eligible_count: number
  }
  missing_information: string[]
}

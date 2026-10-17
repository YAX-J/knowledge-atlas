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

export type WorkspaceNav = 'graph' | 'projects' | 'sources' | 'questions'

export type IngestionOperation = 'projects' | 'create' | 'sources' | 'upload' | 'detail' | 'task' | 'chunks'
export type IngestionLoading = Record<IngestionOperation, boolean>
export type IngestionErrors = Record<IngestionOperation, string>
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
  evidence: CandidateEvidence[]
  source_candidate_id: string | null
  target_candidate_id: string | null
  created_at: string
  updated_at: string
}

export interface ReviewDecision {
  id: string
  action: 'confirm' | 'reject'
  changes?: { name?: string; summary?: string }
}

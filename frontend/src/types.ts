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

export type WorkspaceNav = 'graph' | 'projectGraph' | 'projects' | 'sources' | 'questions'

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
  knowledge_id: string | null
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

export interface FormalEvidence extends CandidateEvidence {
  id: string
  source_id: string
  title: string
  uri: string
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

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

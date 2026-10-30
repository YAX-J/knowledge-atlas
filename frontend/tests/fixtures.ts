import type { ApiProject, ApiSource } from '../src/api/knowledgeAtlas'
import type { IngestionErrors, IngestionLoading, IngestionOperation, QuestionAnswer } from '../src/types'

export const project: ApiProject = {
  id: 'project-1', name: 'Synthetic project', description: 'Public test fixture',
  created_at: '2026-10-24T00:00:00Z', updated_at: '2026-10-24T00:00:00Z',
}
export const source: ApiSource = {
  id: 'source-1', project_id: project.id, repository_id: null, repository_name: null, git_url: null,
  original_name: 'main.py', relative_path: null, media_type: 'text/plain', source_type: 'python',
  size_bytes: 12, content_sha256: 'a'.repeat(64), status: 'ready', content_preview: 'a.save()', line_count: 1,
  created_at: project.created_at, updated_at: project.updated_at,
}
const operations: IngestionOperation[] = ['projects', 'create', 'repositories', 'remote', 'sync', 'activity',
  'commit', 'sources', 'upload', 'detail', 'task', 'chunks', 'structure', 'agent']
export const loading = Object.fromEntries(operations.map(key => [key, false])) as IngestionLoading
export const errors = Object.fromEntries(operations.map(key => [key, ''])) as IngestionErrors

export function answerFixture(): QuestionAnswer {
  return { id:'answer',question:'Storage and performance?',supported:false,confidence:.8,
    answer:'Storage.\n\nPerformance is unknown.',answer_protocol:'evidence-claims-v2',
    claims:[{text:'<script>Storage.</script>',status:'supported',citation_ids:['quote-b','quote-a']},
      {text:'Performance is unknown.',status:'insufficient',citation_ids:[]}],
    entity_ids:['entity'],missing_information:['Benchmark evidence.'],
    evidence:['a','b'].map(id=>({id:`quote-${id}`,entity_id:'entity',entity_name:'Storage',
      source_id:`source-${id}`,chunk_id:`chunk-${id}`,title:`${id}-${'long-path/'.repeat(12)}file.md`,uri:'local',
      git_url:null,quote:'Source text',start_line:2,end_line:3,heading_path:[]})),
    retrieval:{keyword_hits:1,vector_hits:0,graph_hits:0,indexed_count:0,eligible_count:1} }
}

import { apiRequest } from './client'
import type { ExtractionResult } from './knowledgeAtlas'
export interface ExtractionPlan {protocol:string;plan_sha256:string;batch_count:number;max_batches:number;chunk_count:number;fragment_count:number;input_chars:number[];input_limit:number;model:string;cached:boolean}
export const getExtractionPlan=(source:string)=>apiRequest<ExtractionPlan>(`/sources/${source}/extraction-plan`)
export const extractBatches=(source:string,plan:string)=>apiRequest<ExtractionResult>(`/sources/${source}/extract?strategy=batched&plan_sha256=${encodeURIComponent(plan)}`,{method:'POST',signal:AbortSignal.timeout(1800000)})

import { expect, it } from 'vitest'
import { associationPath, layoutGraph } from '../src/graphLayout'
import type { FormalKnowledgeEdge, FormalKnowledgeNode } from '../src/types'

const nodes = Array.from({length:12},(_,i)=>({id:String(i),name:`Node ${i}`} as FormalKnowledgeNode))
function edge(id:string,from:number,to:number) { return {id,source_id:String(from),target_id:String(to)} as FormalKnowledgeEdge }
const edges=[edge('first',0,1),edge('second',1,2),edge('cycle',2,0),edge('tail',2,3),edge('self',4,4)]

it('keeps directed cycles bounded and places a downstream component after the cycle',()=>{
  const layout=layoutGraph(nodes,edges,'directed')
  expect(layout.positions.size).toBe(nodes.length)
  expect(layout.positions.get('3')!.x).toBeGreaterThan(layout.positions.get('2')!.x)
  expect(layout.positions.get('0')!.x).toBe(layout.positions.get('2')!.x)
  for (const point of layout.positions.values()) {
    expect(Number.isFinite(point.x+point.y)).toBe(true)
    expect(point.x).toBeGreaterThan(0);expect(point.x).toBeLessThan(layout.width)
    expect(point.y).toBeGreaterThan(0);expect(point.y).toBeLessThan(layout.height)
  }
})

it('produces stable topology and non-overlapping node footprints despite input order and disconnected nodes',()=>{
  const first=layoutGraph(nodes,edges,'topology'),second=layoutGraph([...nodes].reverse(),[...edges].reverse(),'topology')
  expect([...first.positions]).toEqual([...second.positions])
  const points=[...first.positions.values()]
  for(let a=0;a<points.length;a++) for(let b=a+1;b<points.length;b++) {
    expect(Math.abs(points[a]!.x-points[b]!.x)>=239 || Math.abs(points[a]!.y-points[b]!.y)>=144).toBe(true)
  }
  expect(layoutGraph([],[],'topology').positions.size).toBe(0)
})

it('finds a shortest undirected association only among the supplied edges',()=>{
  expect(associationPath(edges,'3','0')).toEqual(['tail','cycle'])
  expect(associationPath(edges.filter(item=>item.id!=='tail'),'3','0')).toBeNull()
  expect(associationPath(edges,'0','0')).toEqual([])
  expect(associationPath(edges,'0','11')).toBeNull()
  expect(associationPath(edges,'','0')).toBeNull()
})

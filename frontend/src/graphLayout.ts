import type { FormalKnowledgeEdge, FormalKnowledgeNode } from './types'

export type GraphLayoutMode = 'topology' | 'directed'
export interface GraphPoint { x: number; y: number }
export interface GraphLayout { width: number; height: number; positions: Map<string, GraphPoint> }

/** Stable bounded layout for the API's at-most-200-node visible subgraph. */
export function layoutGraph(nodes: FormalKnowledgeNode[], edges: FormalKnowledgeEdge[], mode: GraphLayoutMode): GraphLayout {
  const ordered = [...nodes].sort((a,b) => a.id.localeCompare(b.id))
  const ids = new Set(ordered.map(node => node.id))
  const links = edges.filter(edge => ids.has(edge.source_id) && ids.has(edge.target_id) && edge.source_id !== edge.target_id)
    .sort((a,b) => a.id.localeCompare(b.id))
  if (!ordered.length) return { width:740, height:300, positions:new Map() }
  const points = new Map<string, GraphPoint>()
  if (mode === 'directed') {
    // Collapse cycles before assigning ranks, so cyclic input cannot grow ranks forever.
    const adjacent = new Map(ordered.map(node => [node.id, [] as string[]]))
    for (const edge of links) adjacent.get(edge.source_id)!.push(edge.target_id)
    const seen = new Map<string,number>(), low = new Map<string,number>(), stack:string[] = [], active = new Set<string>()
    const groups:string[][] = []
    let index = 0
    function visit(id:string) {
      seen.set(id,index); low.set(id,index++); stack.push(id); active.add(id)
      for (const target of adjacent.get(id)!) {
        if (!seen.has(target)) { visit(target); low.set(id,Math.min(low.get(id)!,low.get(target)!)) }
        else if (active.has(target)) low.set(id,Math.min(low.get(id)!,seen.get(target)!))
      }
      if (low.get(id) === seen.get(id)) {
        const group:string[] = []
        let member:string
        do { member=stack.pop()!; active.delete(member); group.push(member) } while (member !== id)
        groups.push(group.sort())
      }
    }
    for (const node of ordered) if (!seen.has(node.id)) visit(node.id)
    const owners = new Map(groups.flatMap((group,i) => group.map(id => [id,i] as const)))
    const outgoing = groups.map(() => new Set<number>()), incoming = groups.map(() => 0), ranks = groups.map(() => 0)
    for (const edge of links) {
      const from=owners.get(edge.source_id)!, to=owners.get(edge.target_id)!
      if (from !== to && !outgoing[from]!.has(to)) { outgoing[from]!.add(to); incoming[to]!++ }
    }
    const queue=incoming.flatMap((count,i) => count === 0 ? [i] : [])
    for (let offset=0;offset<queue.length;offset++) {
      const current=queue[offset]!
      for (const next of outgoing[current]!) {
        ranks[next]=Math.max(ranks[next]!,ranks[current]!+1)
        if (--incoming[next]! === 0) queue.push(next)
      }
    }
    const rows=new Map<number,string[]>()
    for (const node of ordered) {
      const rank=ranks[owners.get(node.id)!]!
      rows.set(rank,[...(rows.get(rank) ?? []),node.id])
    }
    const maxRows=Math.max(...[...rows.values()].map(row=>row.length))
    for (const [rank,row] of rows) row.forEach((id,i)=>points.set(id,{x:140+rank*280,y:110+(maxRows-row.length)*80+i*160}))
  } else {
    const radius=Math.max(180,Math.sqrt(ordered.length)*85)
    ordered.forEach((node,i)=>points.set(node.id,{x:Math.cos(i*2*Math.PI/ordered.length)*radius*1.5,y:Math.sin(i*2*Math.PI/ordered.length)*radius*.65}))
    // Fixed iterations avoid simulation timers and respect reduced-motion preferences.
    for (let iteration=0;iteration<140;iteration++) {
      const alpha=1-iteration/160
      const forces=new Map(ordered.map(node=>[node.id,{x:0,y:0}]))
      for (let a=0;a<ordered.length;a++) for (let b=a+1;b<ordered.length;b++) {
        const first=points.get(ordered[a]!.id)!, second=points.get(ordered[b]!.id)!
        const dx=first.x-second.x || .01, dy=first.y-second.y || .01
        const distance=Math.max(1,Math.hypot(dx,dy)), strength=Math.min(35,22000/(distance*distance))
        const fx=dx/distance*strength, fy=dy/distance*strength
        forces.get(ordered[a]!.id)!.x+=fx; forces.get(ordered[a]!.id)!.y+=fy
        forces.get(ordered[b]!.id)!.x-=fx; forces.get(ordered[b]!.id)!.y-=fy
      }
      for (const edge of links) {
        const first=points.get(edge.source_id)!, second=points.get(edge.target_id)!
        const dx=second.x-first.x,dy=second.y-first.y,distance=Math.max(1,Math.hypot(dx,dy))
        const strength=(distance-270)*.025
        const fx=dx/distance*strength,fy=dy/distance*strength
        forces.get(edge.source_id)!.x+=fx; forces.get(edge.source_id)!.y+=fy
        forces.get(edge.target_id)!.x-=fx; forces.get(edge.target_id)!.y-=fy
      }
      for (const node of ordered) {
        const point=points.get(node.id)!,force=forces.get(node.id)!
        point.x+=Math.max(-40,Math.min(40,force.x-point.x*.008))*alpha
        point.y+=Math.max(-40,Math.min(40,force.y-point.y*.008))*alpha
      }
    }
    // Resolve rectangular hit/label footprints after spring placement.
    for (let pass=0;pass<100;pass++) {
      let collided=false
      for (let a=0;a<ordered.length;a++) for (let b=a+1;b<ordered.length;b++) {
        const first=points.get(ordered[a]!.id)!,second=points.get(ordered[b]!.id)!
        const dx=second.x-first.x,dy=second.y-first.y,overlapX=240-Math.abs(dx),overlapY=145-Math.abs(dy)
        if (overlapX>0 && overlapY>0) {
          collided=true
          if (overlapX/240<overlapY/145) { const delta=(overlapX+1)/2*(dx>=0?1:-1); first.x-=delta;second.x+=delta }
          else { const delta=(overlapY+1)/2*(dy>=0?1:-1);first.y-=delta;second.y+=delta }
        }
      }
      if (!collided) break
    }
    // Pack disconnected components rather than leaving isolated nodes around a
    // large empty circle. Preserve spring positions inside each component.
    const neighbors=new Map(ordered.map(node=>[node.id,[] as string[]]))
    for (const edge of links) { neighbors.get(edge.source_id)!.push(edge.target_id);neighbors.get(edge.target_id)!.push(edge.source_id) }
    const visited=new Set<string>(),components:{ids:string[];left:number;top:number;width:number;height:number}[]=[]
    for (const node of ordered) {
      if (visited.has(node.id)) continue
      const members=[node.id];visited.add(node.id)
      for(let i=0;i<members.length;i++) for(const next of neighbors.get(members[i]!)!) if(!visited.has(next)) { visited.add(next);members.push(next) }
      const positions=members.map(id=>points.get(id)!),left=Math.min(...positions.map(p=>p.x)),top=Math.min(...positions.map(p=>p.y))
      components.push({ids:members,left,top,width:Math.max(...positions.map(p=>p.x))-left+260,height:Math.max(...positions.map(p=>p.y))-top+165})
    }
    if(components.length>1) {
      components.sort((a,b)=>b.height-a.height || a.ids[0]!.localeCompare(b.ids[0]!))
      const targetWidth=Math.max(...components.map(c=>c.width),Math.sqrt(components.reduce((sum,c)=>sum+c.width*c.height,0)*2.7))
      let x=0,y=0,rowHeight=0
      for(const component of components) {
        if(x>0 && x+component.width>targetWidth) { x=0;y+=rowHeight;rowHeight=0 }
        for(const id of component.ids) { const p=points.get(id)!;p.x=p.x-component.left+x;p.y=p.y-component.top+y }
        x+=component.width;rowHeight=Math.max(rowHeight,component.height)
      }
    }
  }
  const all=[...points.values()], minX=Math.min(...all.map(point=>point.x)), minY=Math.min(...all.map(point=>point.y))
  for (const point of all) { point.x=point.x-minX+140;point.y=point.y-minY+110 }
  const width=Math.max(740,Math.max(...all.map(point=>point.x))+140),height=Math.max(300,Math.max(...all.map(point=>point.y))+120)
  const paddingX=(width-Math.max(...all.map(point=>point.x))-140)/2,paddingY=(height-Math.max(...all.map(point=>point.y))-120)/2
  for (const point of all) { point.x+=paddingX;point.y+=paddingY }
  return {width,height,positions:points}
}

/** Undirected association path in the displayed subgraph; edge arrows stay intact. */
export function associationPath(edges: FormalKnowledgeEdge[], start:string, end:string): string[] | null {
  if (!start || !end) return null
  if (start===end) return []
  const adjacent=new Map<string,{node:string;edge:string}[]>()
  for (const edge of [...edges].sort((a,b)=>a.id.localeCompare(b.id))) {
    for (const [from,to] of [[edge.source_id,edge.target_id],[edge.target_id,edge.source_id]]) {
      adjacent.set(from!,[...(adjacent.get(from!) ?? []),{node:to!,edge:edge.id}])
    }
  }
  const previous=new Map<string,{node:string;edge:string}>(),queue=[start],seen=new Set(queue)
  for (let i=0;i<queue.length;i++) for (const next of adjacent.get(queue[i]!) ?? []) {
    if (seen.has(next.node)) continue
    seen.add(next.node);previous.set(next.node,{node:queue[i]!,edge:next.edge});queue.push(next.node)
    if (next.node===end) {
      const path:string[]=[]
      let cursor=end
      while (cursor!==start) { const step=previous.get(cursor)!;path.unshift(step.edge);cursor=step.node }
      return path
    }
  }
  return null
}

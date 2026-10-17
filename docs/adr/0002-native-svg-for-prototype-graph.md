# ADR 0002 Native SVG for the prototype graph

- Status: Accepted
- Date: 2026-10-17

## Context

The initial frontend needs to closely reproduce a fixed visual prototype with distinct node shapes, labeled edges, a temporal control, and a small Mock dataset. A full graph library would add bundle weight and layout behavior before real graph-size requirements are known.

## Decision

Use Vue-rendered native SVG for the interactive Mock graph. Keep graph data independent from SVG markup and keep backend contracts free of canvas coordinates.

Re-evaluate AntV G6 or another graph engine when any of these conditions becomes true:

- Typical views exceed approximately 200 visible nodes.
- Automatic force, hierarchy, cluster, or compound-node layouts are required.
- Users need node dragging, lasso selection, minimaps, or progressive graph expansion.
- Performance measurements show SVG rendering is no longer adequate.

## Consequences

- The prototype has deterministic layout and accurate visual styling.
- Keyboard and semantic behavior can be controlled directly.
- Layout, pan, drag, and large-graph performance must be implemented manually if needed early.
- A future graph-library migration should replace only the renderer and view-state layer, not API or domain types.

## Alternatives considered

### AntV G6 immediately

Deferred because current data is small and deterministic, while library configuration would not yet validate real layout requirements.

### Canvas-only custom renderer

Rejected for the prototype because SVG provides simpler text rendering, accessibility hooks, and DOM-based inspection.

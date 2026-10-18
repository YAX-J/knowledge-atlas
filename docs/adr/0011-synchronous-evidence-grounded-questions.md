# ADR 0011 Synchronous evidence-grounded questions with validated citations

- Status: Accepted
- Date: 2026-10-18

## Context

The project has explainable hybrid retrieval and formal evidence, but no real question-answering path. The first answer slice must be auditable, keep external-model input bounded, and avoid inventing a durable conversation model before answer quality is understood. Adding LangGraph, streaming, and question-history tables together would obscure the evidence boundary and enlarge the failure surface.

## Decision

Implement `POST /api/v1/projects/{project_id}/questions` as a synchronous, non-persistent operation. It runs the existing hybrid search with at most five entities, selects at most twelve formal evidence records, and sends only the question plus those evidence records to DeepSeek using a strict JSON schema. An answer may cite at most five evidence UUIDs. The API rejects any citation outside the retrieved set and returns only the cited evidence.

When retrieval produces no evidence, the service returns a deterministic unsupported answer without calling the answer model. Supported model answers require citations; unsupported answers must identify missing information. The current frontend displays only the active result and labels that no history is saved.

This bounded workflow is ordinary deterministic service orchestration. LangGraph, streaming, tool-planning, multi-turn memory, reranking, and question persistence are deferred until a concrete workflow requires them.

## Consequences

- Every returned citation is a currently visible formal evidence record selected before generation.
- Hybrid questioning requires a configured embedding provider and an up-to-date explicit semantic index; evidence-bearing questions additionally require the DeepSeek key.
- Provider failures cannot create partial question records because no question or answer record is written.
- A generated response ID identifies only the response payload and cannot be fetched later.
- Real-provider quality, prompt-injection resistance, latency, and representative graph-bearing retrieval still require acceptance beyond simulated tests.

## Alternatives considered

- Persist questions and answers immediately: rejected until retention, privacy, versioning, and stale-citation semantics are defined.
- Introduce LangGraph for the first call: rejected because the current flow is linear and gains no observable capability from a graph runtime.
- Let the model search or cite arbitrary identifiers: rejected because citation membership could not be enforced at the application boundary.
- Generate an answer when retrieval is empty: rejected because it would permit unsupported model knowledge.

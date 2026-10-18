# ADR 0009: Build the formal-knowledge semantic index explicitly

[简体中文](0009-explicit-semantic-index.zh-CN.md)

- Status: Accepted
- Date: 2026-10-18

## Context

Keyword search locates identifiers and literal source text but cannot recall differently worded questions with similar meaning. The project already uses PostgreSQL/pgvector and needs observable semantic retrieval without coupling external model availability to the formal-knowledge confirmation transaction.

## Decision

Add a separate `knowledge_embeddings` table for formal entities. It stores the SHA-256 of text composed from entity type, name, summary, and evidence quotes, plus the embedding model, a fixed 1024-dimensional vector, and user/project scope. Migration `20261018_0006` owns this schema.

Use a backend-configured OpenAI-compatible `/embeddings` API without selecting a mandatory provider. `POST /api/v1/projects/{project_id}/embeddings/rebuild` explicitly creates or refreshes the index and reuses rows whose model and content hash are unchanged. Confirmation never calls the embedding provider, and index failure does not roll back formal knowledge.

`GET /api/v1/projects/{project_id}/search?mode=vector` embeds the query with the same model and performs exact cosine-distance Top K retrieval through pgvector. Results retain formal entities and source evidence and add similarity plus indexed/eligible counts. Keyword behavior is unchanged; hybrid ranking, graph scores, and answers remain outside this slice.

## Consequences

- Private knowledge is sent to the configured embedding service only after an explicit index rebuild or semantic search.
- Model, dimension, or entity-content changes require a rebuild; the current schema is fixed at 1024 dimensions.
- Exact cosine search is used for the current corpus instead of HNSW/IVFFlat, favoring reproducible ranking.
- SQLite tests persist the same shape and calculate cosine similarity in Python; real PostgreSQL acceptance must still verify pgvector execution.

## Alternatives considered

- Generate vectors during confirmation: rejected because provider failure would enter the authoritative write transaction.
- Require DeepSeek for embeddings: rejected because extraction and embedding are separate interfaces and availability should not be assumed.
- Add hybrid search and the Agent immediately: deferred so semantic retrieval remains independently testable.

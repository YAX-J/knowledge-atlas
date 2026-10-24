"""Fingerprint the actual reviewed graph used by a prepared experiment project."""

from datetime import timezone
import hashlib
import json

from sqlalchemy import select

from app.models.domain import CandidateKnowledge, SourceDocument
from app.models.evolution import KnowledgeChange
from app.models.graph import KnowledgeEmbedding, KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship


def project_snapshot(db, *, user_id, project_id) -> dict:
    """Normalize business UUIDs so independently initialized projects compare equal."""
    sources = list(db.scalars(select(SourceDocument).where(
        SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
    )))
    paths = {item.id: item.relative_path or item.original_name for item in sources}
    candidates = list(db.scalars(select(CandidateKnowledge).where(
        CandidateKnowledge.user_id == user_id, CandidateKnowledge.project_id == project_id,
    )))
    labels = {item.id: f"{paths[item.source_id]}:{item.payload.get('local_id', item.name)}" for item in candidates}

    def timestamp(value):
        if value is None:
            return None
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()

    owners, evidence_labels, records = {}, {}, []
    for model, kind in ((KnowledgeEntity, "entity"), (KnowledgeRelationship, "relationship")):
        items = list(db.scalars(select(model).where(model.user_id == user_id, model.project_id == project_id)))
        for item in items:
            owners[item.id] = labels[item.candidate_id]
        for item in items:
            record = {"kind": kind, "key": labels[item.candidate_id], "type": item.type,
                      "name": item.name, "summary": item.summary, "confidence": item.confidence,
                      "status": item.status, "valid_from": timestamp(item.valid_from),
                      "valid_to": timestamp(item.valid_to)}
            if kind == "relationship":
                record.update(source=owners[item.source_id], target=owners[item.target_id])
            records.append(record)
    for item in db.scalars(select(KnowledgeEvidence).where(
        KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.project_id == project_id,
    )):
        record = {"kind": "evidence", "owner": owners[item.entity_id or item.relationship_id],
                  "source": paths[item.source_id], "start_line": item.start_line,
                  "end_line": item.end_line, "quote": item.quote, "heading_path": item.heading_path}
        evidence_labels[item.id] = record
        records.append(record)
    for item in db.scalars(select(KnowledgeChange).where(
        KnowledgeChange.user_id == user_id, KnowledgeChange.project_id == project_id,
    )):
        records.append({"kind": "change", "new": owners[item.new_entity_id], "old": owners[item.old_entity_id],
                        "type": item.kind, "effective_at": timestamp(item.effective_at),
                        "review_status": item.review_status, "reason": item.reason,
                        "evidence": evidence_labels[item.evidence_id]})
    for item in sources:
        records.append({"kind": "source", "path": paths[item.id], "sha256": item.content_sha256,
                        "type": item.source_type, "status": item.status.value})

    def fingerprint(values):
        serialized = sorted(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in values)
        return hashlib.sha256("\n".join(serialized).encode()).hexdigest()

    index = [{"entity": owners[item.entity_id], "model": item.model,
              "dimensions": item.dimensions, "content_sha256": item.content_sha256,
              "vector": [float(value) for value in item.embedding]}
             for item in db.scalars(select(KnowledgeEmbedding).where(
                 KnowledgeEmbedding.user_id == user_id, KnowledgeEmbedding.project_id == project_id,
             ))]
    return {"knowledge_sha256": fingerprint(records), "index_sha256": fingerprint(index),
            "record_count": len(records), "indexed_entity_count": len(index)}

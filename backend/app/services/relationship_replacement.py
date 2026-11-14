"""Evidence-bound replacement of a service's explicitly identified primary database."""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import aliased

from app.core.names import normalize_name
from app.models.domain import CandidateKnowledge, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeRelationship
from app.schemas.graph import KnowledgeEdgeRead
from app.schemas.knowledge import FactValidity, RelationshipReplacementApproval, RelationshipReplacementRead
from app.services import graph


PRIMARY_DATABASE = "primary_database"


def supported(type_, target_type, source_name, target_name, quotes):
    source_name, target_name = normalize_name(source_name), normalize_name(target_name)
    return type_ == "USES" and target_type == "Technology" and any(
        source_name in quote and target_name in quote and ("主数据库" in quote or "primary database" in quote)
        for quote in map(normalize_name, quotes)
    )


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def preview(db, candidate, endpoints, validity: FactValidity | None):
    if candidate.payload.get("fact_slot") != PRIMARY_DATABASE:
        return None, None
    source = endpoints.get(candidate.payload["source_candidate_id"])
    target = endpoints.get(candidate.payload["target_candidate_id"])
    if source is None or target is None:
        return None, None

    at = validity.valid_from if validity else utc_now()
    old_source, old_target = aliased(KnowledgeEntity), aliased(KnowledgeEntity)
    edge = KnowledgeRelationship
    query = select(edge, old_source, old_target, CandidateKnowledge).join(
        CandidateKnowledge, CandidateKnowledge.id == edge.candidate_id,
    ).join(old_source, old_source.id == edge.source_id).join(old_target, old_target.id == edge.target_id).where(
        edge.user_id == candidate.user_id, edge.project_id == candidate.project_id, edge.type == "USES",
        edge.status != "archived", old_source.type == source.candidate_type, old_target.type == "Technology",
        CandidateKnowledge.user_id == candidate.user_id, CandidateKnowledge.project_id == candidate.project_id,
        or_(CandidateKnowledge.payload["fact_slot"].as_string() == PRIMARY_DATABASE,
            CandidateKnowledge.payload["fact_slot"].as_string().is_(None)),
    )
    if validity and validity.valid_to is not None:
        query = query.where(edge.valid_from < validity.valid_to)
    subject = normalize_name(source.name)
    matches = [
        (old, subject_record, target_record, origin)
        for old, subject_record, target_record, origin in db.execute(query)
        if normalize_name(subject_record.name) == subject and (old.valid_to is None or at < utc(old.valid_to))
        and (origin.payload.get("fact_slot") == PRIMARY_DATABASE or supported(
            old.type, target_record.type, subject_record.name, target_record.name,
            [entry["quote"] for entry in origin.payload.get("evidence", [])],
        ))
    ]
    if not matches:
        return None, None
    if any(normalize_name(item[2].name) == normalize_name(target.name) for item in matches):
        return None, "same_value"
    if validity is None:
        return None, "needs_start"
    if len(matches) != 1:
        return None, "ambiguous"
    old, subject_record, target_record, origin = matches[0]
    if (origin.source_id == candidate.source_id or old.status != "active" or utc(old.valid_from) >= at
            or subject_record.status != "active" or target_record.status == "archived"
            or utc(subject_record.valid_from) > at or utc(target_record.valid_from) > at
            or (target_record.valid_to is not None and utc(target_record.valid_to) <= at)
            or (subject_record.valid_to is not None
                and (validity.valid_to is None or utc(subject_record.valid_to) < validity.valid_to))):
        return None, "ambiguous"
    evidence = graph.evidence_for_records(db, [old], at=at)[old.id]
    if not evidence:
        return None, "ambiguous"
    signature = {
        "candidate": str(candidate.id),
        "old": KnowledgeEdgeRead.model_validate(old).model_dump(mode="json"),
        "validity": validity.model_dump(mode="json"),
        "old_evidence": [item.model_dump(mode="json") for item in evidence],
        "new_evidence": candidate.payload["evidence"],
        "endpoints": [[str(source.id), source.name], [str(target.id), target.name], [str(subject_record.id), subject_record.name]],
    }
    token = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    return RelationshipReplacementRead(
        approval=RelationshipReplacementApproval(old_relationship_id=old.id, token=token),
        old_relationship=KnowledgeEdgeRead.model_validate(old).model_copy(update={
            "name": f"{subject_record.name} → {target_record.name}"[:255],
            "evidence_count": len(evidence),
        }),
        evidence=evidence, effective_at=at,
    ), None

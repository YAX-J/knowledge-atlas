"""OpenAI-compatible embedding transport and explicit project index rebuild."""

import hashlib
import math
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEmbedding, KnowledgeEntity, KnowledgeEvidence
from app.services.projects import get_project
from app.schemas.search import EmbeddingStatusRead


class EmbeddingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _require_configuration(settings: Settings) -> str:
    if not settings.embedding_api_key or not settings.embedding_base_url.strip() or not settings.embedding_model.strip():
        raise EmbeddingError("EMBEDDING_NOT_CONFIGURED", "语义检索尚未配置嵌入服务")
    if settings.embedding_dimensions != 1024:
        raise EmbeddingError("EMBEDDING_DIMENSIONS_INVALID", "当前向量索引固定使用 1024 维嵌入")
    return settings.embedding_api_key.get_secret_value()


def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    key = _require_configuration(settings)
    try:
        response = httpx.post(
            settings.embedding_base_url.rstrip("/") + "/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": settings.embedding_model, "input": texts},
            timeout=httpx.Timeout(settings.embedding_timeout_seconds, connect=10),
            follow_redirects=False,
        )
        if response.status_code != 200:
            message = {
                401: "嵌入服务认证失败，请检查后端 API 密钥",
                402: "嵌入服务余额不足，请检查服务账户",
                429: "嵌入请求受限，请稍后重试",
            }.get(response.status_code, "嵌入服务暂时不可用，请稍后重试")
            raise EmbeddingError("EMBEDDING_PROVIDER_FAILED", message)
        if len(response.content) > 8 * 1024 * 1024:
            raise EmbeddingError("EMBEDDING_OUTPUT_INVALID", "嵌入服务返回内容过大")
        payload = response.json()
        rows = sorted(payload["data"], key=lambda item: item["index"])
        if [row["index"] for row in rows] != list(range(len(texts))):
            raise ValueError("embedding indexes invalid")
        vectors = [item["embedding"] for item in rows]
        if len(vectors) != len(texts):
            raise ValueError("embedding count mismatch")
        for vector in vectors:
            if len(vector) != settings.embedding_dimensions or not any(vector) or not all(
                isinstance(value, (int, float)) and math.isfinite(value) for value in vector
            ):
                raise ValueError("embedding dimensions or values invalid")
        return [[float(value) for value in vector] for vector in vectors]
    except EmbeddingError:
        raise
    except httpx.HTTPError as exc:
        raise EmbeddingError("EMBEDDING_PROVIDER_FAILED", "嵌入服务连接失败或超时，请稍后重试") from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise EmbeddingError("EMBEDDING_OUTPUT_INVALID", "嵌入服务返回内容不符合接口约定") from exc


def entity_text(entity: KnowledgeEntity, quotes: list[str]) -> str:
    parts = [entity.type, entity.name, entity.summary, *quotes]
    return "\n".join(part.strip() for part in parts if part.strip())


INDEX_STATUS_SCAN_LIMIT = 1000


def project_embedding_status(db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID,
                             settings: Settings, valid_at=None) -> EmbeddingStatusRead:
    from app.services.graph import visible
    get_project(db, user_id=user_id, project_id=project_id)
    at = valid_at or utc_now()
    query = select(KnowledgeEntity).where(*visible(KnowledgeEntity, user_id, project_id, at))
    eligible = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    joined = query.join(KnowledgeEmbedding, KnowledgeEmbedding.entity_id == KnowledgeEntity.id).where(
        KnowledgeEmbedding.user_id == user_id, KnowledgeEmbedding.project_id == project_id,
        KnowledgeEmbedding.model == settings.embedding_model,
        KnowledgeEmbedding.dimensions == settings.embedding_dimensions,
    )
    indexed = db.scalar(select(func.count()).select_from(joined.subquery())) or 0
    entities = list(db.scalars(query.order_by(KnowledgeEntity.id).limit(INDEX_STATUS_SCAN_LIMIT)))
    ids = [entity.id for entity in entities]
    existing = {item.entity_id: item for item in db.scalars(select(KnowledgeEmbedding).where(
        KnowledgeEmbedding.entity_id.in_(ids), KnowledgeEmbedding.user_id == user_id,
        KnowledgeEmbedding.project_id == project_id, KnowledgeEmbedding.model == settings.embedding_model,
        KnowledgeEmbedding.dimensions == settings.embedding_dimensions,
    ))} if ids else {}
    quotes = {}
    if existing:
        for owner, quote in db.execute(select(KnowledgeEvidence.entity_id, KnowledgeEvidence.quote).where(
            KnowledgeEvidence.entity_id.in_(existing), KnowledgeEvidence.user_id == user_id,
            KnowledgeEvidence.project_id == project_id,
        ).order_by(KnowledgeEvidence.id)):
            quotes.setdefault(owner, []).append(quote)
    current = stale = 0
    for entity in entities:
        embedding = existing.get(entity.id)
        if embedding is not None:
            digest = hashlib.sha256(entity_text(entity, quotes.get(entity.id, [])).encode('utf-8')).hexdigest()
            if digest == embedding.content_sha256:
                current += 1
            else:
                stale += 1
    try:
        _require_configuration(settings)
        configured = True
    except EmbeddingError:
        configured = False
    return EmbeddingStatusRead(model=settings.embedding_model, dimensions=settings.embedding_dimensions,
        configured=configured, checked_at=utc_now(), eligible_count=eligible, indexed_count=indexed,
        missing_count=eligible-indexed, stale_count=stale, current_count=current,
        scanned_count=len(entities), scan_limit=INDEX_STATUS_SCAN_LIMIT, truncated=eligible > len(entities))


def rebuild_project_embeddings(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, settings: Settings,
) -> dict:
    get_project(db, user_id=user_id, project_id=project_id)
    try:
        _require_configuration(settings)
    except EmbeddingError as exc:
        raise AppError(status_code=503, code=exc.code, message=exc.message) from exc

    entities = list(db.scalars(select(KnowledgeEntity).where(
        KnowledgeEntity.user_id == user_id,
        KnowledgeEntity.project_id == project_id,
        KnowledgeEntity.status != "archived",
    ).order_by(KnowledgeEntity.id)))
    existing = {row.entity_id: row for row in db.scalars(select(KnowledgeEmbedding).where(
        KnowledgeEmbedding.user_id == user_id,
        KnowledgeEmbedding.project_id == project_id,
    ))}
    pending: list[tuple[KnowledgeEntity, str, str]] = []
    for entity in entities:
        quotes = list(db.scalars(select(KnowledgeEvidence.quote).where(
            KnowledgeEvidence.entity_id == entity.id,
            KnowledgeEvidence.user_id == user_id,
            KnowledgeEvidence.project_id == project_id,
        ).order_by(KnowledgeEvidence.id)))
        text = entity_text(entity, quotes)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        current = existing.get(entity.id)
        if not current or current.model != settings.embedding_model or current.dimensions != settings.embedding_dimensions or current.content_sha256 != digest:
            pending.append((entity, text, digest))

    # Release the read transaction before the external request. Persistence is
    # serialized only after vectors return, so project writes are not blocked by network latency.
    db.commit()
    vectors: list[list[float]] = []
    try:
        for offset in range(0, len(pending), settings.embedding_batch_size):
            batch = pending[offset:offset + settings.embedding_batch_size]
            vectors.extend(embed_texts(settings, [item[1] for item in batch]))
    except EmbeddingError as exc:
        raise AppError(status_code=503, code=exc.code, message=exc.message) from exc

    if pending:
        project = db.scalar(select(Project).where(
            Project.id == project_id, Project.user_id == user_id, Project.archived_at.is_(None),
        ).with_for_update())
        if project is None:
            raise AppError(status_code=404, code="PROJECT_NOT_FOUND", message="项目不存在")
    current = {row.entity_id: row for row in db.scalars(select(KnowledgeEmbedding).where(
        KnowledgeEmbedding.entity_id.in_([item[0].id for item in pending]),
        KnowledgeEmbedding.user_id == user_id,
        KnowledgeEmbedding.project_id == project_id,
    ))} if pending else {}
    for (entity, _, digest), vector in zip(pending, vectors, strict=True):
        row = current.get(entity.id)
        if row is None:
            row = KnowledgeEmbedding(entity_id=entity.id, user_id=user_id, project_id=project_id)
            db.add(row)
        row.model = settings.embedding_model
        row.dimensions = settings.embedding_dimensions
        row.content_sha256 = digest
        row.embedding = vector
    db.commit()
    return {
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimensions,
        "eligible_count": len(entities),
        "updated_count": len(pending),
        "reused_count": len(entities) - len(pending),
    }

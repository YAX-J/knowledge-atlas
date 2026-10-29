"""Time-aware identity projection; original entities, edges and quotes stay intact."""
from sqlalchemy import func, or_, select

from app.models.workspace import EntityAlias, EntityMerge
from app.core.names import normalize_name as normalized


def active_merge(user_id, project_id, at):
    return (EntityMerge.user_id == user_id, EntityMerge.project_id == project_id,
            EntityMerge.valid_from <= at, or_(EntityMerge.valid_to.is_(None), EntityMerge.valid_to > at))


def canonical(column, user_id, project_id, at):
    return func.coalesce(select(EntityMerge.target_id).where(
        *active_merge(user_id, project_id, at), EntityMerge.source_id == column,
    ).correlate_except(EntityMerge).scalar_subquery(), column)


def mapping(db, user_id, project_id, at):
    return dict(db.execute(select(EntityMerge.source_id, EntityMerge.target_id).where(
        *active_merge(user_id, project_id, at))).all())


def alias_names(db, user_id, project_id, at, ids):
    result = {}
    if not ids:
        return result
    target = canonical(EntityAlias.entity_id, user_id, project_id, at)
    for entity_id, name in db.execute(select(target, EntityAlias.name).where(
        EntityAlias.user_id == user_id, EntityAlias.project_id == project_id,
        EntityAlias.created_at <= at, target.in_(ids))):
        result.setdefault(entity_id, []).append(name)
    return result

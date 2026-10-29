"""Select a coherent immutable commit or explicit local versions before any provider call."""
from collections import defaultdict
from types import SimpleNamespace
from sqlalchemy import select
from app.core.errors import AppError
from app.models.domain import RepositorySnapshot, RepositorySnapshotFile, SourceDocument

METADATA_LIMIT = 2000


def _error(code, message, status=409):
    raise AppError(status_code=status, code=code, message=message)


def _snapshot_choices(db, source):
    return list(db.scalars(select(RepositorySnapshot).where(
        RepositorySnapshot.user_id==source.user_id, RepositorySnapshot.project_id==source.project_id,
        RepositorySnapshot.repository_id==source.repository_id,
        RepositorySnapshot.id.in_(select(RepositorySnapshotFile.snapshot_id).where(
            RepositorySnapshotFile.source_id==source.id,RepositorySnapshotFile.status.notin_(['deleted','skipped'])))).order_by(
        RepositorySnapshot.created_at.desc(),RepositorySnapshot.id).limit(51))) if source.repository_id else []


def _metadata(db, source, compatible):
    return list(db.execute(select(SourceDocument.id,SourceDocument.relative_path,SourceDocument.original_name,
        SourceDocument.size_bytes,SourceDocument.created_at).where(
        SourceDocument.user_id==source.user_id, SourceDocument.project_id==source.project_id,
        SourceDocument.repository_id==source.repository_id, SourceDocument.source_type.in_(tuple(compatible)),
        SourceDocument.status=='ready').order_by(SourceDocument.created_at.desc(),SourceDocument.id.desc())
        .limit(METADATA_LIMIT+1)))


def describe(db, source, compatible):
    snapshots=_snapshot_choices(db,source)
    groups=defaultdict(list)
    metadata=_metadata(db,source,compatible)
    for item in metadata[:METADATA_LIMIT]:
        path=item.relative_path or item.original_name
        if path!=(source.relative_path or source.original_name):
            groups[path].append(dict(id=item.id,created_at=item.created_at,size_bytes=item.size_bytes))
    preferred=next((item for item in snapshots[:50] if not item.truncated),snapshots[0] if snapshots else None)
    return dict(default_snapshot_id=preferred.id if preferred else None,
        snapshots=[dict(id=item.id,commit_sha=item.commit_sha,ref=item.ref,truncated=item.truncated) for item in snapshots[:50]],
        version_groups=[dict(path=path,versions=values[:20],truncated=len(values)>20) for path,values in sorted(groups.items()) if len(values)>1][:100],
        truncated=len(metadata)>METADATA_LIMIT or len(snapshots)>50 or sum(len(values)>1 for values in groups.values())>100)


def _view(document,path):
    return SimpleNamespace(id=document.id,relative_path=path,original_name=path.rsplit('/',1)[-1],
        content=document.content,source_type=document.source_type,size_bytes=document.size_bytes)


def select_context(db,source,compatible,*,snapshot_id=None,version_ids=None,max_sources=99,max_bytes=20*1024*1024):
    choices=_snapshot_choices(db,source)
    if snapshot_id is not None:
        snapshot=db.scalar(select(RepositorySnapshot).where(RepositorySnapshot.id==snapshot_id,
            RepositorySnapshot.user_id==source.user_id,RepositorySnapshot.project_id==source.project_id,
            RepositorySnapshot.repository_id==source.repository_id))
        if snapshot is None:_error('ANALYSIS_SNAPSHOT_NOT_FOUND','分析快照不存在或不属于此仓库',404)
    else:
        snapshot=next((item for item in choices if not item.truncated),choices[0] if choices else None)
    if snapshot is not None:
        if version_ids:_error('ANALYSIS_CONTEXT_INVALID','固定提交不能混入本地版本选择')
        rows=list(db.execute(select(RepositorySnapshotFile.path,SourceDocument.id,SourceDocument.size_bytes,SourceDocument.status).join(SourceDocument,
            SourceDocument.id==RepositorySnapshotFile.source_id).where(
            RepositorySnapshotFile.snapshot_id==snapshot.id,RepositorySnapshotFile.status.notin_(['deleted','skipped']),
            SourceDocument.user_id==source.user_id,SourceDocument.project_id==source.project_id,
            SourceDocument.repository_id==source.repository_id,
            SourceDocument.source_type.in_(tuple(compatible))).order_by(RepositorySnapshotFile.path).limit(METADATA_LIMIT+1)))
        selected=[item for item in rows if item.id==source.id and item.status=='ready']
        if len(selected)!=1:_error('ANALYSIS_SOURCE_NOT_IN_SNAPSHOT','请选择包含当前来源唯一文件路径的快照')
        if len({item.id for item in rows})!=len(rows):
            _error('ANALYSIS_SNAPSHOT_PATH_AMBIGUOUS','同一来源在快照中映射到多个路径，需分别导入以核验声明身份')
        main=_view(source,selected[0].path)
        paths={};used=source.size_bytes;truncated=snapshot.truncated or len(rows)>METADATA_LIMIT
        for item in rows[:METADATA_LIMIT]:
            if item.id==source.id:continue
            if item.status!='ready' or len(paths)>=max_sources or used+item.size_bytes>max_bytes:
                truncated=True;continue
            paths[item.id]=item.path;used+=item.size_bytes
        documents={item.id:item for item in db.scalars(select(SourceDocument).where(SourceDocument.id.in_(paths)))} if paths else {}
        related=[_view(documents[identifier],path) for identifier,path in paths.items()]
        return main,related,truncated,dict(snapshot_id=snapshot.id,commit_sha=snapshot.commit_sha,policy='fixed_commit')
    metadata=_metadata(db,source,compatible)
    by_id={item.id:item for item in metadata[:METADATA_LIMIT]}
    overrides={}
    for identifier in version_ids or []:
        item=by_id.get(identifier)
        if item is None:_error('ANALYSIS_VERSION_NOT_FOUND','所选版本不在当前仓库的可分析范围',404)
        path=item.relative_path or item.original_name
        if path in overrides or path==(source.relative_path or source.original_name):
            _error('ANALYSIS_CONTEXT_INVALID','每个相关文件只能选择一个版本，当前文件保持所选版本')
        overrides[path]=item
    chosen={}
    for item in metadata[:METADATA_LIMIT]:
        path=item.relative_path or item.original_name
        if path!=(source.relative_path or source.original_name):chosen.setdefault(path,overrides.get(path,item))
    identifiers=[];used=source.size_bytes;truncated=len(metadata)>METADATA_LIMIT
    for path,item in chosen.items():
        if len(identifiers)>=max_sources or used+item.size_bytes>max_bytes:
            truncated=True;continue
        identifiers.append(item.id);used+=item.size_bytes
    if not set(version_ids or []).issubset(identifiers):
        _error('ANALYSIS_CONTEXT_LIMIT','所选版本超出分析预算，请缩小仓库范围')
    documents={item.id:item for item in db.scalars(select(SourceDocument).where(SourceDocument.id.in_(identifiers)))} if identifiers else {}
    return source,[documents[key] for key in identifiers],truncated,dict(snapshot_id=None,commit_sha=None,policy='local_latest_with_explicit_overrides')

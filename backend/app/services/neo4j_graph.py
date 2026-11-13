import uuid
from datetime import datetime

from neo4j import Driver, GraphDatabase, ManagedTransaction, Query, unit_of_work
from neo4j.exceptions import DriverError, Neo4jError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import utc_now
from app.schemas.graph import GraphRead, Neo4jGraphRead, Neo4jGraphSync
from app.services import graph
from app.services.projects import get_project


ENTITY_CONSTRAINT = """
CREATE CONSTRAINT knowledge_entity_id IF NOT EXISTS
FOR (node:KnowledgeEntity) REQUIRE node.id IS UNIQUE
"""
PROJECT_PATTERN = "(p:KAProjectProjection {id: $project_id, user_id: $user_id})"
SCOPE_PROPERTIES = "user_id: $user_id, project_id: $project_id"
BATCH_SIZE = 500


def _driver(settings: Settings) -> Driver:
    password = settings.neo4j_password
    if password is None or not password.get_secret_value():
        raise AppError(status_code=503, code="NEO4J_NOT_CONFIGURED", message="请在后端配置 Neo4j 连接信息")
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, password.get_secret_value()),
        connection_timeout=5, connection_acquisition_timeout=10, max_transaction_retry_time=0,
    )


def _connection_error() -> AppError:
    return AppError(status_code=503, code="NEO4J_UNAVAILABLE", message="Neo4j 操作失败，请检查连接、数据库与权限")


def check_connection(settings: Settings) -> None:
    try:
        with _driver(settings) as driver:
            with driver.session(database=settings.neo4j_database) as session:
                session.run(Query("RETURN 1 AS ok", timeout=5)).single(strict=True)
    except (DriverError, Neo4jError, ValueError):
        raise _connection_error() from None


@unit_of_work(timeout=30)
def _replace_snapshot(
    tx: ManagedTransaction, scope: dict[str, str], data: GraphRead, at: datetime, revision: str,
) -> None:
    nodes = [dict(node.model_dump(mode="json"), position=position) for position, node in enumerate(data.nodes)]
    edges = [dict(edge.model_dump(mode="json"), position=position) for position, edge in enumerate(data.edges)]
    tx.run(f"""
        MATCH (:KAProjectionEntity {{{SCOPE_PROPERTIES}}})
            -[edge:KA_RELATIONSHIP {{{SCOPE_PROPERTIES}}}]->(:KAProjectionEntity {{{SCOPE_PROPERTIES}}})
        DELETE edge
        """, scope).consume()
    for start in range(0, len(nodes), BATCH_SIZE):
        tx.run("""
            UNWIND $rows AS row
            MERGE (node:KnowledgeEntity:KAProjectionEntity {
                id: row.id, user_id: $user_id, project_id: $project_id
            })
            SET node += row, node.revision = $revision
            """, scope, rows=nodes[start:start + BATCH_SIZE], revision=revision).consume()
    tx.run(f"""
        MATCH (node:KAProjectionEntity {{{SCOPE_PROPERTIES}}})
        WHERE node.revision IS NULL OR node.revision <> $revision
        DELETE node
        """, scope, revision=revision).consume()
    for start in range(0, len(edges), BATCH_SIZE):
        batch = edges[start:start + BATCH_SIZE]
        record = tx.run(f"""
            UNWIND $rows AS row
            MATCH (source:KnowledgeEntity:KAProjectionEntity {{{SCOPE_PROPERTIES}, id: row.source_id}})
            MATCH (target:KnowledgeEntity:KAProjectionEntity {{{SCOPE_PROPERTIES}, id: row.target_id}})
            CREATE (source)-[edge:KA_RELATIONSHIP]->(target)
            SET edge = row, edge.user_id = $user_id
            RETURN count(edge) AS written
            """, scope, rows=batch).single(strict=True)
        if record["written"] != len(batch):
            raise AppError(status_code=409, code="NEO4J_PROJECTION_INVALID", message="图谱快照存在缺失端点")
    tx.run(f"""
        MERGE {PROJECT_PATTERN}
        SET p.valid_at = $valid_at
        """, scope, valid_at=at.isoformat()).consume()


def sync_project(
    db: Session, settings: Settings, *, user_id: uuid.UUID, project_id: uuid.UUID, valid_at: datetime | None,
) -> Neo4jGraphSync:
    get_project(db, user_id=user_id, project_id=project_id, lock=True)
    at = valid_at or utc_now()
    try:
        with _driver(settings) as driver:
            data = graph.read_projection(db, user_id=user_id, project_id=project_id, at=at)
            with driver.session(database=settings.neo4j_database) as session:
                session.run(Query(ENTITY_CONSTRAINT, timeout=15)).consume()
                scope = {"user_id": str(user_id), "project_id": str(project_id)}
                session.execute_write(_replace_snapshot, scope, data, at, uuid.uuid4().hex)
    except (DriverError, Neo4jError, ValueError):
        raise _connection_error() from None
    return Neo4jGraphSync(valid_at=at, node_count=len(data.nodes), edge_count=len(data.edges))


@unit_of_work(timeout=15)
def _read_snapshot(
    tx: ManagedTransaction, scope: dict[str, str], center_id: str | None,
    depth: int, types: list[str], limit: int,
) -> Neo4jGraphRead:
    marker = tx.run(f"MATCH {PROJECT_PATTERN} RETURN p.valid_at AS valid_at", scope).single()
    if marker is None:
        raise AppError(status_code=409, code="NEO4J_PROJECTION_MISSING", message="请先同步项目图谱快照")

    truncated = False
    if center_id is None:
        nodes = tx.run(f"""
            MATCH (node:KAProjectionEntity {{{SCOPE_PROPERTIES}}})
            WHERE $types = [] OR node.type IN $types
            RETURN properties(node) AS node ORDER BY node.position LIMIT $limit
            """, scope, types=types, limit=limit + 1).value("node")
        truncated = len(nodes) > limit
        nodes = nodes[:limit]
    else:
        center = tx.run(f"""
            MATCH (node:KnowledgeEntity:KAProjectionEntity {{{SCOPE_PROPERTIES}, id: $center_id}})
            WHERE $types = [] OR node.type IN $types
            RETURN properties(node) AS node
            """, scope, center_id=center_id, types=types).single()
        if center is None:
            raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="中心知识不存在或不符合当前筛选条件")
        nodes = [center["node"]]
        frontier, visited = [center_id], {center_id}
        for _ in range(depth):
            remaining = limit - len(nodes)
            neighbors = tx.run(f"""
                UNWIND $frontier AS node_id
                MATCH (start:KnowledgeEntity:KAProjectionEntity {{{SCOPE_PROPERTIES}, id: node_id}})
                    -[:KA_RELATIONSHIP {{{SCOPE_PROPERTIES}}}]-(node:KAProjectionEntity {{{SCOPE_PROPERTIES}}})
                WHERE NOT node.id IN $visited AND ($types = [] OR node.type IN $types)
                WITH DISTINCT node
                RETURN properties(node) AS node ORDER BY node.position LIMIT $limit
                """, scope, frontier=frontier, visited=list(visited), types=types, limit=remaining + 1).value("node")
            truncated = truncated or len(neighbors) > remaining
            found = neighbors[:remaining]
            nodes.extend(found)
            frontier = [node["id"] for node in found]
            visited.update(frontier)
            if not frontier:
                break

    ids = [node["id"] for node in nodes]
    edges = tx.run(f"""
        UNWIND $ids AS node_id
        MATCH (source:KnowledgeEntity:KAProjectionEntity {{{SCOPE_PROPERTIES}, id: node_id}})
            -[edge:KA_RELATIONSHIP {{{SCOPE_PROPERTIES}}}]->(target:KAProjectionEntity {{{SCOPE_PROPERTIES}}})
        WHERE target.id IN $ids
        RETURN properties(edge) AS edge ORDER BY edge.position LIMIT $limit
        """, scope, ids=ids, limit=graph.MAX_EDGES + 1).value("edge")
    return Neo4jGraphRead(
        nodes=[{"valid_to": None, **node} for node in nodes],
        edges=[{"valid_to": None, **edge} for edge in edges[:graph.MAX_EDGES]],
        truncated=truncated or len(edges) > graph.MAX_EDGES,
        valid_at=marker["valid_at"],
    )


def read_project(
    db: Session, settings: Settings, *, user_id: uuid.UUID, project_id: uuid.UUID,
    center_id: uuid.UUID | None, depth: int, types: list[str], limit: int,
) -> Neo4jGraphRead:
    get_project(db, user_id=user_id, project_id=project_id, lock=True)
    scope = {"user_id": str(user_id), "project_id": str(project_id)}
    try:
        with _driver(settings) as driver:
            with driver.session(database=settings.neo4j_database) as session:
                return session.execute_read(_read_snapshot, scope, str(center_id) if center_id else None, depth, types, limit)
    except (DriverError, Neo4jError, ValueError):
        raise _connection_error() from None

"""Readiness checks physical ownership as well as the migration marker."""
from sqlalchemy import inspect, text

EXPECTED_REVISION = '20261026_0018'
WORKSPACE_TABLES = frozenset({'entity_aliases', 'entity_merges', 'knowledge_periods',
    'knowledge_operations', 'conversations', 'conversation_turns'})


def schema_status(db):
    inspector = inspect(db.connection())
    schema = inspector.default_schema_name
    tables = set(inspector.get_table_names(schema=schema))
    if 'alembic_version' not in tables:
        return False, 'database migrations have not been applied'
    quoted_schema = db.get_bind().dialect.identifier_preparer.quote(schema) if schema else None
    version_table = f'{quoted_schema}.alembic_version' if quoted_schema else 'alembic_version'
    revisions = list(db.scalars(text(f'SELECT version_num FROM {version_table}')))
    if revisions != [EXPECTED_REVISION]:
        return False, f'database migration required; expected {EXPECTED_REVISION}'
    if not WORKSPACE_TABLES.issubset(tables) or 'repository_snapshots' not in tables:
        return False, 'database schema is incomplete; apply or repair migrations'
    columns = {item['name'] for item in inspector.get_columns('repository_snapshots', schema=schema)}
    if 'scan_state' not in columns:
        return False, 'database schema is incomplete; apply or repair migrations'
    return True, None

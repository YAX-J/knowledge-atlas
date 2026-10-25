"""Native PostgreSQL backup and fresh-database restore with snapshot fingerprints.

Credentials remain in child-process environment, never argv or reports.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from psycopg import Error as PsycopgError

from sqlalchemy import MetaData, create_mock_engine, create_engine, text
from pgvector.sqlalchemy import Vector  # Registers PostgreSQL vector reflection.
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import make_url

from app.core.config import get_settings


class BackupValidationError(ValueError):
    """A safe, operator-facing validation message with no database contents."""


def executable(name, bin_dir=None):
    suffix = '.exe' if os.name == 'nt' else ''
    candidates = [Path(bin_dir) / (name + suffix)] if bin_dir else []
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    if os.name == 'nt' and not bin_dir:
        candidates.extend(sorted(Path('C:/Program Files/PostgreSQL').glob(f'*/bin/{name}.exe'), reverse=True))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    raise BackupValidationError(f'PostgreSQL executable unavailable: {name}; pass --bin-dir')


def pg_environment(url, database=None):
    url = make_url(url)
    if url.get_backend_name() != 'postgresql' or url.query:
        raise BackupValidationError('Use a PostgreSQL URL without connection query overrides')
    env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    env.update(PGHOST=url.host or 'localhost', PGPORT=str(url.port or 5432), PGUSER=url.username or '',
               PGPASSWORD=url.password or '', PGDATABASE=database or url.database or '', PGCONNECT_TIMEOUT='10')
    return env


def invoke(args, env):
    result = subprocess.run(args, env=env, capture_output=True, check=False)
    if result.returncode:
        # pg tools/SQL errors can include private names or connection details.
        raise RuntimeError(f'{Path(args[0]).stem} failed (exit {result.returncode}); no database contents logged')


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def constraint_definition(value):
    # PostgreSQL can move varchar->text casts inside ARRAY when recreating a CHECK.
    # Normalize ONLY these redundant string casts/literal wrappers, not boolean grouping.
    for cast in ('::character varying', '::text[]', '::text'):
        value = value.replace(cast, '')
    value = re.sub(r"\(('(?:[^']|'')*')\)", r'\1', value)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r'\((ARRAY\[[^\]]*\])\)', r'\1', value)
    return value


def fingerprint(connection, schema=None):
    connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    quote = connection.dialect.identifier_preparer.quote
    rows = connection.execute(text("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') "
        "AND n.nspname NOT LIKE 'pg_toast%' AND (CAST(:schema AS text) IS NULL OR n.nspname=:schema) ORDER BY 1,2"), {'schema':schema}).all()
    tables = {}
    for schema, name in rows:
        qualified = f'{quote(schema)}.{quote(name)}'
        digest, count = hashlib.sha256(), 0
        # Canonical JSONB and database-side sorting retain row multiplicity and avoid Python row buffering.
        stream = connection.execution_options(stream_results=True).execute(text(
            f'SELECT to_jsonb(t)::text FROM {qualified} t ORDER BY to_jsonb(t)::text COLLATE "C"'))
        for row in stream:
            payload = row[0].encode('utf-8')
            digest.update(len(payload).to_bytes(8, 'big'))
            digest.update(payload)
            count += 1
        stream.close()
        tables[f'{schema}.{name}'] = {'rows': count, 'sha256': digest.hexdigest()}
    columns = [tuple(row) for row in connection.execute(text(
        "SELECT table_schema,table_name,column_name,data_type,udt_name,is_nullable,column_default "
        "FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') "
        "AND (CAST(:schema AS text) IS NULL OR table_schema=:schema) ORDER BY 1,2,ordinal_position"), {'schema':schema})]
    constraints = [tuple(row) for row in connection.execute(text(
        "SELECT n.nspname,c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k "
        "JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND (CAST(:schema AS text) IS NULL OR n.nspname=:schema) ORDER BY 1,2,3"), {'schema':schema})]
    constraints = [(*row[:3], constraint_definition(row[3])) for row in constraints]
    types = [tuple(row) for row in connection.execute(text(
        "SELECT n.nspname,c.relname,a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_attribute a "
        "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped "
        "AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' "
        "AND (CAST(:schema AS text) IS NULL OR n.nspname=:schema) ORDER BY 1,2,a.attnum"), {'schema':schema})]
    indexes = [tuple(row) for row in connection.execute(text(
        "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema') "
        "AND (CAST(:schema AS text) IS NULL OR schemaname=:schema) ORDER BY 1,2,3"), {'schema':schema})]
    extensions = [tuple(row) for row in connection.execute(text('SELECT extname,extversion FROM pg_extension ORDER BY extname'))]
    unvalidated = connection.scalar(text("SELECT count(*) FROM pg_constraint k JOIN pg_namespace n ON n.oid=k.connamespace "
        "WHERE NOT k.convalidated AND n.nspname NOT IN ('pg_catalog','information_schema') AND (CAST(:schema AS text) IS NULL OR n.nspname=:schema)"), {'schema':schema})
    return dict(tables=tables, columns=columns, types=types, constraints=constraints, indexes=indexes, extensions=extensions,
                unvalidated_constraints=unvalidated)


def backup(url, directory, bin_dir=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    archive, manifest = directory / 'database.dump', directory / 'manifest.json'
    env = pg_environment(url)
    engine = create_engine(url)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            connection.execute(text('SET TRANSACTION READ ONLY'))
            snapshot = connection.scalar(text('SELECT pg_export_snapshot()'))
            if not re.fullmatch(r'[0-9A-Fa-f-]+', snapshot):
                raise BackupValidationError('Invalid exported snapshot identifier')
            invoke([executable('pg_dump', bin_dir), '--no-password', '--format=custom', '--no-owner', '--no-acl',
                    f'--snapshot={snapshot}', f'--file={archive}'], env)
            expected = fingerprint(connection)
            metadata, restored = MetaData(), MetaData()
            metadata.reflect(connection, schema='public')
            for table in metadata.tables.values():
                table.to_metadata(restored, schema='ka_restore_template', referred_schema_fn=lambda *_: 'ka_restore_template')
            statements = []
            mock = create_mock_engine('postgresql+psycopg://', lambda sql, *_a, **_k: statements.append(str(sql.compile(dialect=mock.dialect))))
            restored.create_all(mock, checkfirst=False)
        payload = dict(format='knowledge-atlas-pg-backup-v1', archive_sha256=digest_file(archive), fingerprint=expected, schema_sql=statements)
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return {'directory': str(directory), 'tables': len(expected['tables']), 'verified_archive': True}
    finally:
        engine.dispose()


def validate_archive(directory):
    directory = Path(directory).resolve()
    payload = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if payload.get('format') != 'knowledge-atlas-pg-backup-v1' or digest_file(directory / 'database.dump') != payload.get('archive_sha256'):
        raise BackupValidationError('Backup format or archive checksum mismatch')
    return payload


def restore(url, directory, target, *, bin_dir=None, cleanup=False):
    if not re.fullmatch(r'ka_restore_[a-z0-9_]{1,45}', target):
        raise BackupValidationError('Fresh target must be named ka_restore_<lowercase identifier>')
    source = make_url(url)
    if target == source.database:
        raise BackupValidationError('Cannot restore over the configured application database')
    payload = validate_archive(directory)
    restore_env = pg_environment(url, target)
    admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT')
    created, target_engine = False, None
    try:
        with admin.connect() as connection:
            if connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': target}):
                raise BackupValidationError('Restore target already exists; refusing to overwrite')
            capable = connection.scalar(text('SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname=current_user'))
            if not capable:
                raise BackupValidationError('CREATE DATABASE permission required; use restore-schema for an isolated rehearsal')
            connection.execute(text(f'CREATE DATABASE "{target}" TEMPLATE template0'))
            created = True
        invoke([executable('pg_restore', bin_dir), '--no-password', '--exit-on-error', '--no-owner', '--no-acl',
                '--single-transaction', '--dbname=' + target, str(Path(directory).resolve() / 'database.dump')], restore_env)
        target_engine = create_engine(source.set(database=target))
        with target_engine.connect() as connection:
            actual = fingerprint(connection)
        # JSON round-trip normalizes tuples from native SQL results.
        if json.loads(json.dumps(actual)) != payload['fingerprint']:
            raise BackupValidationError('Restored database fingerprint differs from backup')
        if actual['unvalidated_constraints']:
            raise BackupValidationError('Restored database has unvalidated constraints')
        return dict(target=target, integrity='passed', tables=len(actual['tables']), cleaned=cleanup)
    finally:
        if target_engine:
            target_engine.dispose()
        if created and cleanup:
            with admin.connect() as connection:
                # Only the validated fresh target created by THIS invocation is eligible.
                connection.execute(text(f'DROP DATABASE "{target}"'))
        admin.dispose()


def restore_schema(url, directory, target, *, bin_dir=None, cleanup=False):
    """Application public-schema rehearsal when the role cannot CREATE DATABASE."""
    if not re.fullmatch(r'ka_restore_[a-z0-9_]{1,45}', target):
        raise BackupValidationError('Fresh schema must be named ka_restore_<lowercase identifier>')
    payload = validate_archive(directory)
    if not payload.get('schema_sql') or any(not name.startswith('public.') for name in payload['fingerprint']['tables']):
        raise BackupValidationError('Schema rehearsal requires a public-only application backup with saved DDL')
    directory = Path(directory).resolve()
    data_file = directory / f'.restore-data-{uuid.uuid4().hex}.sql'
    engine, created = create_engine(url), False
    quote = engine.dialect.identifier_preparer.quote
    try:
        with engine.begin() as connection:
            if connection.scalar(text('SELECT 1 FROM information_schema.schemata WHERE schema_name=:schema'), {'schema':target}):
                raise BackupValidationError('Restore schema already exists; refusing to overwrite')
            connection.execute(text(f'CREATE SCHEMA "{target}"'))
        created = True
        with engine.begin() as connection:
            connection.execute(text(f'SET LOCAL search_path="{target}",public'))
            for statement in payload['schema_sql']:
                connection.execute(text(statement.replace('ka_restore_template', target)))
            owned = set(connection.scalars(text('SELECT table_name FROM information_schema.tables WHERE table_schema=:schema'), {'schema':target}))
            expected = {name.split('.',1)[1] for name in payload['fingerprint']['tables']}
            if owned != expected:
                raise BackupValidationError('Restored schema must physically own every expected table before copying data')
            foreign = connection.scalar(text('SELECT count(*) FROM pg_constraint k JOIN pg_namespace n ON n.oid=k.connamespace '
                'JOIN pg_class r ON r.oid=k.confrelid JOIN pg_namespace rn ON rn.oid=r.relnamespace '
                "WHERE k.contype='f' AND n.nspname=:schema AND rn.nspname<>:schema"), {'schema':target})
            if foreign:
                raise BackupValidationError('Restore schema foreign keys must never reference application tables')
        invoke([executable('pg_restore', bin_dir), '--data-only', '--no-owner', '--no-acl', f'--file={data_file}',
                str(directory / 'database.dump')], pg_environment(url))
        with engine.begin() as connection:
            connection.execute(text(f'SET LOCAL search_path="{target}",public'))
            cursor = connection.connection.driver_connection.cursor()
            entries = {}
            with data_file.open('rb') as stream:
                while line := stream.readline():
                    if not line.startswith(b'COPY '):
                        continue
                    match = re.fullmatch(rb'COPY public\.([a-z_][a-z0-9_]*) \(([^)]+)\) FROM stdin;\r?\n', line)
                    if not match:
                        raise BackupValidationError('Unsupported COPY header; no data copied to public')
                    name = match[1].decode()
                    columns = [part.strip().strip('"') for part in match[2].decode().split(',')]
                    if name not in expected or name in entries or any(not re.fullmatch(r'[a-z_][a-z0-9_]*', part) for part in columns):
                        raise BackupValidationError('COPY table/column outside the recorded application schema')
                    begin = stream.tell()
                    while True:
                        end = stream.tell()
                        data = stream.readline()
                        if not data:
                            raise BackupValidationError('Incomplete COPY stream')
                        if data.rstrip(b'\r\n') == b'\\.':
                            break
                    entries[name] = columns, begin, end
                order = []
                for statement in payload['schema_sql']:
                    match = re.search(r'CREATE TABLE ka_restore_template\.([a-z_][a-z0-9_]*)', statement)
                    if match:
                        order.append(match[1])
                if set(order) != expected or set(entries) != expected:
                    raise BackupValidationError('Every recorded table must have one COPY block and one saved table definition')
                for name in order:
                    columns, begin, end = entries[name]
                    stream.seek(begin)
                    with cursor.copy(f'COPY "{target}".{quote(name)} ({",".join(quote(part) for part in columns)}) FROM STDIN') as copy:
                        while stream.tell() < end:
                            copy.write(stream.read(min(1024 * 1024, end - stream.tell())))
            cursor.close()
            actual = fingerprint(connection, schema=target)
        normalized = json.loads(json.dumps(actual).replace(target, 'public'))
        if normalized != payload['fingerprint'] or actual['unvalidated_constraints']:
            raise BackupValidationError('Schema rehearsal fingerprint mismatch')
        return dict(target_schema=target, integrity='passed', tables=len(expected), cleaned=cleanup)
    finally:
        if data_file.exists():
            assert data_file.resolve().parent == directory
            data_file.unlink()
        if created and cleanup:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{target}" CASCADE'))
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore', 'restore-schema'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--target', help='New database named ka_restore_<name>; existing targets are rejected')
    parser.add_argument('--cleanup', action='store_true', help='Drop only the fresh restore target after verification')
    parser.add_argument('--bin-dir', type=Path)
    args = parser.parse_args()
    try:
        url = get_settings().database_url
        if args.action == 'backup':
            if args.cleanup or args.target:
                raise BackupValidationError('Target/cleanup apply only to restore')
            result = backup(url, args.directory, args.bin_dir)
        else:
            if not args.target:
                raise BackupValidationError('--target is required for restore')
            operation = restore_schema if args.action == 'restore-schema' else restore
            result = operation(url, args.directory, args.target, bin_dir=args.bin_dir, cleanup=args.cleanup)
        print(json.dumps(result))
        return 0
    except (ValueError, RuntimeError, OSError, SQLAlchemyError, PsycopgError) as error:
        message = str(error) if isinstance(error, BackupValidationError) else type(error).__name__
        print(f'Backup operation failed: {message}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

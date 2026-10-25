import json

import pytest

from scripts import database_backup as backup


def test_backup_credentials_only_enter_environment_and_connection_overrides_are_rejected():
    env = backup.pg_environment('postgresql+psycopg://user:private-value@localhost:5432/app', 'ka_restore_test')
    assert env['PGPASSWORD'] == 'private-value' and env['PGDATABASE'] == 'ka_restore_test'
    for url in ('sqlite:///test.db', 'postgresql://localhost/app?options=unsafe'):
        with pytest.raises(ValueError):
            backup.pg_environment(url)


def test_restore_rejects_existing_application_or_unsafe_targets_before_connecting(tmp_path):
    for target in ('public', 'postgres', 'app', 'ka_restore_a";drop database app', '../ka_restore_test'):
        with pytest.raises(ValueError):
            backup.restore('postgresql://localhost/app', tmp_path, target)


def test_manifest_checksum_rejects_truncated_or_modified_archives(tmp_path):
    archive = tmp_path / 'database.dump'
    archive.write_bytes(b'PGDMP-local-fixture')
    payload = dict(format='knowledge-atlas-pg-backup-v1', archive_sha256=backup.digest_file(archive), fingerprint={})
    (tmp_path / 'manifest.json').write_text(json.dumps(payload))
    assert backup.validate_archive(tmp_path) == payload
    archive.write_bytes(b'changed')
    with pytest.raises(ValueError):
        backup.validate_archive(tmp_path)


def test_tool_failure_never_echoes_private_stderr(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(backup.subprocess, 'run', lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr=b'private-value'))
    with pytest.raises(RuntimeError) as failure:
        backup.invoke(['pg_dump'], {})
    assert 'private-value' not in str(failure.value)


def test_constraint_fingerprints_normalize_redundant_string_casts_without_losing_boolean_groups():
    left = "CHECK (((state)::text = ANY ((ARRAY['open'::character varying, 'closed'::character varying])::text[])))"
    right = "CHECK (((state)::text = ANY (ARRAY[('open'::character varying)::text, ('closed'::character varying)::text])))"
    assert backup.constraint_definition(left) == backup.constraint_definition(right)
    assert backup.constraint_definition('(a OR b) AND c') != backup.constraint_definition('a OR (b AND c)')

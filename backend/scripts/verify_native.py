r"""Migrate/test an isolated PostgreSQL schema, then remove only that schema.

Run from backend: .\.venv\Scripts\python.exe -m scripts.verify_native
Uses DATABASE_URL / .env without printing it. Requires an existing vector extension
in public and CREATE SCHEMA permission. Never migrates the application's schema.
"""
import os
import argparse
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.db.base import Base
from app import models

from app.core import config as app_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github", action="store_true", help="Explicitly allow read-only public petclinic acceptance; never call models")
    args = parser.parse_args()
    base = make_url(app_config.get_settings().database_url)
    if base.get_backend_name() != "postgresql":
        raise RuntimeError("Native acceptance requires PostgreSQL")
    schema = "ka_acceptance_" + uuid.uuid4().hex
    assert re.fullmatch(r"ka_acceptance_[0-9a-f]{32}", schema)
    admin = create_engine(base, connect_args={"connect_timeout": 5})
    url = base.set(query={**base.query, "options": f"-csearch_path={schema},public"})
    rendered = url.render_as_string(hide_password=False)
    previous_settings = app_config.get_settings
    created = False
    try:
        with admin.begin() as connection:
            vector = connection.scalar(text("SELECT extversion FROM pg_extension JOIN pg_namespace n ON n.oid=extnamespace "
                                            "WHERE extname='vector' AND n.nspname='public'"))
            if vector is None:
                raise RuntimeError("Install pgvector in public before running native acceptance")
            version = connection.scalar(text("SHOW server_version"))
            public_revision = connection.scalar(text("SELECT version_num FROM public.alembic_version")) if connection.scalar(
                text("SELECT to_regclass('public.alembic_version')")) else None
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        print(f"Native PostgreSQL {version}; pgvector {vector}; isolated schema created", flush=True)
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "migrations"))
        config.attributes["version_table_schema"] = schema
        app_config.get_settings = lambda: SimpleNamespace(database_url=rendered.replace("%", "%%"))
        command.upgrade(config, "head")
        schema_engine = create_engine(url)
        try:
            with schema_engine.connect() as connection:
                # Fail before tests if even one business table fell through to public.
                assert connection.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema=:schema "
                                              "AND table_name IN ('projects','knowledge_entities','knowledge_changes','source_documents','alembic_version')"),
                                         {"schema": schema}) == 5
                assert connection.scalar(text(f'SELECT count(*) FROM "{schema}".projects')) == 0
                owned = set(connection.scalars(text('SELECT table_name FROM information_schema.tables WHERE table_schema=:schema'), {'schema':schema}))
                assert set(Base.metadata.tables).issubset(owned), 'All business tables must physically belong to the disposable schema'
        finally:
            schema_engine.dispose()
        command.downgrade(config, "20261022_0014")
        command.upgrade(config, "head")
        print("Native migration upgrade/downgrade/upgrade: PASS", flush=True)
        env = {**os.environ, "DATABASE_URL": rendered, "KA_ACCEPTANCE_SCHEMA": schema}
        tests = ["tests/test_evolution.py", "tests/test_stage_four_workflow.py", "tests/test_native_acceptance.py",
                 "tests/test_prepare_evaluation.py", "tests/test_lexical_search.py", "tests/test_batched_lexical.py",
                 "tests/test_retrieval_optimization.py", "tests/test_maintenance_optimization.py",
                 "tests/test_batch_reviews.py", "tests/test_embedding_status.py", "tests/test_knowledge_discovery.py",
                 "tests/test_source_filters.py", "tests/test_embedding_jobs.py", "tests/test_source_retrieval.py",
                 "tests/test_read_performance.py", "tests/test_retirement.py", "tests/test_workspace_completion.py",
                 "tests/test_conversations.py", "tests/test_answer_claims.py", "tests/test_github_continuation.py", "tests/test_project_workflow.py",
                 "tests/test_code_context.py", "tests/test_embedding_plan.py", "tests/test_holdout_v3.py", "tests/test_multi_agent.py", "tests/test_agent_tools.py", "tests/test_agent_progress.py", "tests/test_agent_scope.py"]
        if args.github:
            env["KA_GITHUB_ACCEPTANCE"] = "1"
            report = root.parent / "output" / "native-acceptance" / f"github-{uuid.uuid4().hex}.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            env["KA_GITHUB_REPORT"] = str(report)
            tests.append("tests/test_github_public_acceptance.py")
            print(f"Explicit public GitHub read-only acceptance enabled; report: {report}", flush=True)
        # Providers are stubbed inside these tests. No API key or URL is passed in argv.
        result = subprocess.run([sys.executable, "-m", "pytest", *tests, "-o", "addopts=", "-q", "--tb=short", "--show-capture=no"],
                                cwd=root, env=env, check=False)
        return result.returncode
    finally:
        app_config.get_settings = previous_settings
        if created:
            # The target is generated, checked above, and was created by this process.
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                after = connection.scalar(text("SELECT version_num FROM public.alembic_version")) if connection.scalar(
                    text("SELECT to_regclass('public.alembic_version')")) else None
                assert after == public_revision, "Application migration marker changed during isolated acceptance"
            print("Disposable acceptance schema removed; application migration marker unchanged", flush=True)
        admin.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Connection strings and provider credentials must not appear in a traceback.
        print(f"Native acceptance failed ({type(exc).__name__}); inspect local configuration without exposing credentials.", file=sys.stderr)
        raise SystemExit(1)

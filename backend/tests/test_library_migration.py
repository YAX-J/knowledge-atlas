from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.models.domain import Project, SourceDocument
from app.models.library import SourceArchive


def configuration():
    root=Path(__file__).resolve().parents[1]
    config=Config(str(root/'alembic.ini'))
    config.set_main_option('script_location',str(root/'migrations'))
    return config


def test_library_upgrade_downgrade_preserves_existing_sources(tmp_path,monkeypatch):
    url='sqlite:///'+(tmp_path/'library.sqlite3').as_posix()
    monkeypatch.setattr(app_config,'get_settings',lambda:SimpleNamespace(database_url=url))
    config=configuration();command.upgrade(config,'20261031_0023')
    engine=create_engine(url)
    with Session(engine) as db:
        project=Project(user_id=uuid.uuid4(),name='Existing project')
        db.add(project);db.flush()
        source=SourceDocument(user_id=project.user_id,project_id=project.id,original_name='keep.md',
            source_type='markdown',media_type='text/markdown',content='Keep original',size_bytes=13,content_sha256='a'*64)
        db.add(source);db.commit();source_id=source.id;project_id=project.id;user_id=project.user_id
    command.upgrade(config,'head')
    assert {'source_archives','answer_feedback'}.issubset(inspect(engine).get_table_names())
    with Session(engine) as db:
        assert db.get(SourceDocument,source_id).content=='Keep original'
        db.add(SourceArchive(source_id=source_id,user_id=user_id,project_id=project_id,archived=True,reason='Test'))
        db.commit()
    command.downgrade(config,'20261031_0023')
    assert 'source_archives' not in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(SourceDocument,source_id).content=='Keep original'
        assert db.get(Project,project_id).name=='Existing project'
    command.upgrade(config,'head')
    with Session(engine) as db:
        assert list(db.scalars(select(SourceArchive)))==[]
        assert db.get(SourceDocument,source_id).id==source_id
    engine.dispose()


def test_library_postgresql_migration_compiles_without_connection(monkeypatch):
    monkeypatch.setattr(app_config,'get_settings',lambda:SimpleNamespace(database_url='postgresql+psycopg://unused/unused'))
    config=configuration();output=StringIO();config.output_buffer=output
    command.upgrade(config,'20261031_0023:head',sql=True)
    sql=output.getvalue()
    assert 'CREATE TABLE source_archives' in sql and 'CREATE TABLE answer_feedback' in sql
    assert 'ix_feedback_turn_created' in sql and 'ck_feedback_category' in sql
    assert 'DROP TABLE source_documents' not in sql

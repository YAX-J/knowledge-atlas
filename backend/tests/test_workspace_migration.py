import uuid
from types import SimpleNamespace
from alembic import command
from sqlalchemy import create_engine, inspect, text
from app.core import config as app_config
from tests.test_migrations import migration_config

def test_notes_and_governed_operations_upgrade_preserves_tasks_and_downgrade_closes_new_work(tmp_path,monkeypatch):
    url=f"sqlite+pysqlite:///{(tmp_path/'workspace.db').as_posix()}"
    monkeypatch.setattr(app_config,'get_settings',lambda:SimpleNamespace(database_url=url))
    cfg=migration_config();command.upgrade(cfg,'20261031_0021');engine=create_engine(url)
    project=uuid.uuid4().hex;user=uuid.uuid4().hex;task=uuid.uuid4().hex
    with engine.begin() as db:
        db.execute(text('INSERT INTO projects (id,user_id,name,description) VALUES (:id,:user,:name,:description)'),dict(id=project,user=user,name='Existing',description='kept'))
        db.execute(text("INSERT INTO assistant_tasks (id,user_id,project_id,status,input_sha256,request,events,usage) VALUES (:id,:user,:project,'succeeded',:hash,:request,'[]','{}')"),dict(id=task,user=user,project=project,hash='a'*64,request='{"goal":"Existing"}'))
    command.upgrade(cfg,'head')
    assert {'notes','note_revisions','note_sources','assistant_operations','assistant_approvals'}<=set(inspect(engine).get_table_names())
    with engine.begin() as db:
        assert db.scalar(text('SELECT status FROM assistant_tasks'))=='succeeded'
        db.execute(text("UPDATE assistant_tasks SET execution_mode='async_v3',status='waiting_approval'"))
    command.downgrade(cfg,'20261031_0021')
    assert 'notes' not in inspect(engine).get_table_names()
    with engine.connect() as db:
        assert db.scalar(text('SELECT status FROM assistant_tasks'))=='interrupted'
        assert db.scalar(text('SELECT name FROM projects'))=='Existing'
    command.upgrade(cfg,'head');engine.dispose()

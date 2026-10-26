"""Own an explicitly migrated native schema; never fall through to application tables."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app import models
from app.core import config as configuration
from app.db.base import Base


@contextmanager
def isolated_workspace(settings):
    base=make_url(settings.database_url)
    if base.get_backend_name()!='postgresql':
        raise ValueError('Native PostgreSQL is required')
    schema='ka_functional_'+uuid.uuid4().hex
    admin=create_engine(base,connect_args={'connect_timeout':5})
    engine=None
    created=False
    previous=configuration.get_settings
    try:
        with admin.begin() as connection:
            marker=connection.scalar(text('SELECT version_num FROM public.alembic_version')) if connection.scalar(text("SELECT to_regclass('public.alembic_version')")) else None
            if not connection.scalar(text("SELECT 1 FROM pg_extension JOIN pg_namespace n ON n.oid=extnamespace WHERE extname='vector' AND n.nspname='public'")):
                raise RuntimeError('pgvector must already exist in public')
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created=True
        url=base.set(query={**base.query,'options':f'-csearch_path={schema},public'})
        native=settings.model_copy(update={'database_url':url.render_as_string(hide_password=False)})
        root=Path(__file__).resolve().parents[1]
        config=Config(str(root/'alembic.ini'))
        config.set_main_option('script_location',str(root/'migrations'))
        config.attributes['version_table_schema']=schema
        configuration.get_settings=lambda:SimpleNamespace(database_url=native.database_url.replace('%','%%'))
        command.upgrade(config,'head')
        configuration.get_settings=previous
        engine=create_engine(url,connect_args={'connect_timeout':5})
        with engine.connect() as connection:
            tables=set(connection.scalars(text('SELECT table_name FROM information_schema.tables WHERE table_schema=:schema'),{'schema':schema}))
            if not set(Base.metadata.tables).issubset(tables):
                raise RuntimeError('All business tables must be physically owned by the private schema')
            if connection.scalar(text(f'SELECT count(*) FROM "{schema}".projects')):
                raise RuntimeError('Disposable schema must start empty')
        yield engine,native,schema
    finally:
        configuration.get_settings=previous
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                after=connection.scalar(text('SELECT version_num FROM public.alembic_version')) if connection.scalar(text("SELECT to_regclass('public.alembic_version')")) else None
                if after!=marker:
                    raise RuntimeError('Application migration marker changed')
        admin.dispose()

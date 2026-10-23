from collections.abc import Generator
import os
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    schema = os.environ.get("KA_ACCEPTANCE_SCHEMA")
    if schema:
        # Enabled only by scripts.verify_native, never against the application's schema.
        assert re.fullmatch(r"ka_acceptance_[0-9a-f]{32}", schema)
        url = make_url(os.environ["DATABASE_URL"])
        assert url.get_backend_name() == "postgresql"
        assert url.query.get("options") == f"-csearch_path={schema},public"
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                assert connection.scalar(text("select current_schema()")) == schema
                assert connection.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema=:schema "
                                              "AND table_name IN ('projects','knowledge_entities','source_documents','knowledge_changes')"),
                                         {"schema": schema}) == 4
                connection.rollback()
                transaction = connection.begin()
                try:
                    with Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
                        yield session
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()
        return
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    with testing_session() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


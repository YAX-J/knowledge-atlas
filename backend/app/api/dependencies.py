import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db


# Authentication is intentionally deferred. Keeping a stable user boundary now
# avoids changing every persistence model when real authentication is added.
DEVELOPMENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id() -> uuid.UUID:
    return DEVELOPMENT_USER_ID


DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]


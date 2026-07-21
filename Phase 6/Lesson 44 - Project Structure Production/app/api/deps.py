"""api/deps.py - shared HTTP-layer dependencies.

Re-exports get_db and holds any cross-route dependencies (pagination params,
current-user, etc.). Routes import their dependencies from here.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.base import get_db

# A tidy alias routes can use for the DB session.
DB = Annotated[Session, Depends(get_db)]

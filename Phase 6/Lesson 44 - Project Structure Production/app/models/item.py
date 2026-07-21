"""models/item.py - the SQLAlchemy model (a database table).

Persistence only. No HTTP, no business rules - just the table definition.
"""

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    sku: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))

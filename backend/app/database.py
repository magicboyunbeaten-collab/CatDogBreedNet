"""SQLite database engine, session factory and FastAPI session dependency."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def init_db(db_path: Path) -> sessionmaker:
    """Create the engine, ensure tables exist and return a session factory."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path.resolve().as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False,
                        class_=Session)


def get_db(request: Request):
    """Yield a database session and always close it afterwards.

    Routes own the transaction boundaries (commit / rollback); this
    dependency only guarantees the session is closed.
    """
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()

from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def init_db() -> None:
    """Create tables if they do not exist yet. Alembic migrations are the source of truth in production;
    this is only a convenience for local/dev bootstrapping."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

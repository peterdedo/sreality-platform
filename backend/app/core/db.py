from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings

# Explicit pool knobs (SQLAlchemy defaults are 5+10/30s). Documented for the
# single-worker Railway layout: one long-lived scrape Session plus concurrent
# HTTP handlers share this pool; pool_pre_ping recovers after Postgres blips.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=60,
    pool_recycle=1800,
)


def init_db() -> None:
    """Create tables if they do not exist yet. Alembic migrations are the source of truth in production;
    this is only a convenience for local/dev bootstrapping."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

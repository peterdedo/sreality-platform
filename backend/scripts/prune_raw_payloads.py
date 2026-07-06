"""One-off / ops helper: prune duplicate list raw_payload rows to free disk space."""

from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine


def prune_duplicate_list_raw_payloads(session: Session) -> int:
    """Keep only the newest list payload per hash_id; delete older duplicates."""
    result = session.execute(
        text(
            """
            DELETE FROM rawpayload
            WHERE payload_type = 'list'
              AND id NOT IN (
                SELECT DISTINCT ON (hash_id) id
                FROM rawpayload
                WHERE payload_type = 'list' AND hash_id IS NOT NULL
                ORDER BY hash_id, fetched_at DESC
              )
            """
        )
    )
    session.commit()
    return result.rowcount or 0


def vacuum_raw_payload_table(session: Session) -> None:
    """Reclaim disk after large deletes (requires autocommit connection)."""
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        # VACUUM cannot run inside a transaction block.
        with bind.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("VACUUM ANALYZE rawpayload"))


if __name__ == "__main__":
    with Session(engine) as session:
        deleted = prune_duplicate_list_raw_payloads(session)
        print(f"Deleted {deleted} duplicate list raw_payload row(s)")
        vacuum_raw_payload_table(session)
        print("VACUUM ANALYZE rawpayload done")

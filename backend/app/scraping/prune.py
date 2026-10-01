"""Prune archival list-type raw payloads to reclaim disk space."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine

logger = logging.getLogger(__name__)


def _vacuum_rawpayload() -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("VACUUM ANALYZE rawpayload"))


def prune_list_raw_payloads(session: Session) -> int:
    """Delete ``payload_type='list'`` rows and VACUUM. Returns deleted row count."""
    deleted = session.execute(text("DELETE FROM rawpayload WHERE payload_type = 'list'")).rowcount or 0
    session.commit()
    if deleted:
        logger.info("Pruned %d list rawpayload row(s); running VACUUM ANALYZE", deleted)
        _vacuum_rawpayload()
    else:
        logger.info("No list rawpayload rows to prune")
    return int(deleted)

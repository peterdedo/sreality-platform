"""Metadata for separating analytics truth (full local DB) from UI presentation.

Every aggregate endpoint should document that it scans the full stored dataset.
List/table endpoints may accept an optional ``limit`` for browser rendering only;
when omitted, all matching rows are returned.
"""

FULL_LOCAL_DATASET = "full_local_dataset"
UI_PRESENTATION = "ui_presentation"


def analytics_meta(*, scope: str = FULL_LOCAL_DATASET, **extra) -> dict:
    payload = {"data_scope": scope, **extra}
    return payload

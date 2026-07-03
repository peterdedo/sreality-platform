"""Shared FastAPI dependencies.

require_api_key guards state-changing / heavy endpoints (scrape trigger,
analytics recompute, exports) behind a single shared secret sent as the
`X-API-Key` request header. This is deliberately a single-key scheme, not
user accounts/roles -- it matches the current single-operator maturity of
the platform (see the audit's Theme 1). The expected key comes from
Settings.api_key, which fails loud at startup if left at its dev default in
production (see app/core/config.py).
"""

from fastapi import Header, HTTPException, status

from app.core.config import settings

API_KEY_HEADER = "X-API-Key"


def require_api_key(x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Neplatný nebo chybějící API klíč.",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )

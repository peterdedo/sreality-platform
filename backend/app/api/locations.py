from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.db import get_session
from app.models import Location

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", summary="Seznam lokalit")
def list_locations(session: Session = Depends(get_session)):
    return session.exec(select(Location)).all()

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.cities_models import City

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("")
def list_cities(db: Session = Depends(get_db)):
    return (
        db.query(City)
        .filter(City.is_active == True)  # noqa: E712
        .order_by(City.title.asc())
        .all()
    )
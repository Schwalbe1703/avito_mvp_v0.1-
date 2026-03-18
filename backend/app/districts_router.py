from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.cities_models import City, District
from app.ads_schemas import DistrictOut

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("", response_model=list[DistrictOut])
def list_districts(
    city: str = Query(..., description="City slug, e.g. spb"),
    db: Session = Depends(get_db),
):
    city_obj = db.execute(select(City).where(City.slug == city)).scalar_one_or_none()
    if not city_obj:
        raise HTTPException(status_code=404, detail="City not found")

    rows = db.execute(
        select(District)
        .where(District.city_id == city_obj.id)
        .order_by(District.title.asc())
    ).scalars().all()

    return [DistrictOut(slug=d.slug, title=d.title) for d in rows]
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ads_models import Ad, Review


def recompute_ad_rating(db: Session, ad_id):
    cnt, avg = (
        db.query(func.count(Review.id), func.avg(Review.rating))
        .filter(
            Review.ad_id == ad_id,
            Review.is_published == True,  # noqa: E712
        )
        .one()
    )

    avg_val = float(avg) if avg is not None else 0.0
    avg_val = round(avg_val, 2)

    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if ad:
        ad.rating_count = int(cnt or 0)
        ad.rating_avg = avg_val
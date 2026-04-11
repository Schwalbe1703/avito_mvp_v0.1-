from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.ads_models import Ad, AdPhoto, Category, Subscription
from app.ads_schemas import (
    AdCreate,
    AdDetail,
    AdOut,
    AdOwnerDetail,
    AdUpdate,
    CabinetActionFlags,
    CabinetAdItemOut,
    CabinetMasterSummary,
    CabinetSubscriptionOut,
    MasterCabinetOut,
    MyAdsStats,
    RevealPhoneResponse,
)
from app.auth import get_current_user
from app.cities_models import City, District
from app.deps import get_db

router = APIRouter(prefix="/ads", tags=["ads"])

PHOTOS_TRIGGER_MODERATION = False
MAX_PHOTO_SIZE_MB = 8
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}

MSK = ZoneInfo("Europe/Moscow")


def api_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details,
        },
    )


def require_master(user):
    if getattr(user, "role", None) != "master":
        raise api_error(403, "forbidden", "Доступ разрешён только мастеру")
    return user


def get_category_by_slug(db: Session, slug: str) -> Category | None:
    return db.query(Category).filter(Category.slug == slug).first()


def get_city_by_slug(db: Session, slug: str) -> City | None:
    return (
        db.query(City)
        .filter(City.slug == slug, City.is_active == True)  # noqa: E712
        .first()
    )


def public_visible_query(q):
    return (
        q.join(
            Subscription,
            (Subscription.master_id == Ad.master_id) & (Subscription.category_id == Ad.category_id),
        )
        .filter(
            Ad.status == "approved",
            Ad.is_active == True,  # noqa: E712
            Ad.archived_at.is_(None),
            Subscription.grace_until >= func.now(),
        )
    )


def ad_load_options():
    return (
        joinedload(Ad.city_rel),
        joinedload(Ad.districts_rel),
        joinedload(Ad.photos),
    )


def normalize_ru_phone(raw: str | None) -> str | None:
    if raw is None:
        return None

    s = raw.strip()
    if not s:
        return None

    digits = re.sub(r"\D", "", s)

    if len(digits) == 11 and digits.startswith("8"):
        return "+7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits

    return None


def mask_ru_phone(normalized: str) -> str:
    if not normalized:
        return ""
    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) ***-**-{digits[-2:]}"
    if len(normalized) <= 4:
        return "*" * len(normalized)
    return f"{normalized[:3]} *** ** {normalized[-2:]}"


def enrich_city_fields(ad: Ad) -> dict:
    city_slug = None
    city_title = None
    if getattr(ad, "city_rel", None) is not None:
        city_slug = getattr(ad.city_rel, "slug", None)
        city_title = getattr(ad.city_rel, "title", None)
    return {"city_slug": city_slug, "city_title": city_title}


def enrich_districts_fields(ad: Ad) -> dict:
    districts = []
    for d in getattr(ad, "districts_rel", []) or []:
        districts.append(
            {
                "slug": getattr(d, "slug", None),
                "title": getattr(d, "title", None),
            }
        )
    return {"districts": districts}


def enrich_photos_fields(ad: Ad) -> dict:
    photos = []
    cover = None
    items = getattr(ad, "photos", []) or []

    for p in items:
        photos.append({"id": p.id, "url": p.url, "sort_order": p.sort_order})

    if items:
        cover = items[0].url

    return {"photos": photos, "cover_url": cover}


def to_ad_out(ad: Ad) -> AdOut:
    data = AdOut.model_validate(ad).model_dump()
    data.update(enrich_city_fields(ad))
    data.update(enrich_districts_fields(ad))
    data.update(enrich_photos_fields(ad))
    return AdOut(**data)


def to_ad_detail(ad: Ad) -> AdDetail:
    masked = None
    if getattr(ad, "show_phone", False) and getattr(ad, "contact_phone", None):
        masked = mask_ru_phone(ad.contact_phone)

    data = AdDetail.model_validate(ad).model_dump()
    data.update(enrich_city_fields(ad))
    data.update(enrich_districts_fields(ad))
    data.update(enrich_photos_fields(ad))
    data["contact_phone_masked"] = masked
    return AdDetail(**data)


def to_ad_owner_detail(ad: Ad) -> AdOwnerDetail:
    data = AdOwnerDetail.model_validate(ad).model_dump()
    data.update(enrich_city_fields(ad))
    data.update(enrich_districts_fields(ad))
    data.update(enrich_photos_fields(ad))
    data["contact_phone"] = getattr(ad, "contact_phone", None)
    data["show_phone"] = bool(getattr(ad, "show_phone", False))
    return AdOwnerDetail(**data)


def get_owned_ad(db: Session, master_id, ad_id: UUID) -> Ad | None:
    return (
        db.query(Ad)
        .options(*ad_load_options())
        .filter(Ad.id == ad_id, Ad.master_id == master_id)
        .first()
    )


def get_public_ad(db: Session, ad_id: UUID) -> Ad | None:
    return (
        public_visible_query(db.query(Ad))
        .options(*ad_load_options())
        .filter(Ad.id == ad_id)
        .first()
    )


def validate_and_fetch_districts(
    db: Session,
    city_id,
    district_slugs: list[str],
) -> list[District]:
    slugs = list(dict.fromkeys([s.strip() for s in district_slugs if s and s.strip()]))
    if not slugs:
        return []

    districts = (
        db.query(District)
        .filter(District.city_id == city_id, District.slug.in_(slugs))
        .all()
    )
    found = {d.slug for d in districts}
    missing = [s for s in slugs if s not in found]

    if missing:
        raise api_error(
            400,
            "unknown_district_slugs",
            "Переданы неизвестные районы",
            {"unknown_district_slugs": missing},
        )

    return districts


def validate_status_filter(status: str) -> str:
    allowed = {"moderation", "approved", "blocked"}
    if status not in allowed:
        raise api_error(
            422,
            "invalid_status_filter",
            "Недопустимый статус фильтра",
            {"allowed": sorted(allowed)},
        )
    return status


def build_my_ads_stats(db: Session, master_id) -> MyAdsStats:
    rows = (
        db.query(Ad.status, Ad.archived_at, Ad.is_active)
        .filter(Ad.master_id == master_id)
        .all()
    )

    stats = MyAdsStats()
    stats.total = len(rows)

    for status, archived_at, is_active in rows:
        if status == "approved":
            stats.approved += 1
        elif status == "moderation":
            stats.moderation += 1
        elif status == "blocked":
            stats.blocked += 1

        if archived_at is not None:
            stats.archived += 1
        if is_active:
            stats.active += 1

    return stats


def get_subscription_flags(sub: Subscription | None, now_utc: datetime) -> dict:
    paid_until = getattr(sub, "paid_until", None) if sub else None
    grace_until = getattr(sub, "grace_until", None) if sub else None

    is_paid_active = bool(paid_until and paid_until >= now_utc)
    is_grace_active = bool((not is_paid_active) and grace_until and grace_until >= now_utc)
    is_visible_now = bool(grace_until and grace_until >= now_utc)

    return {
        "has_subscription": sub is not None,
        "paid_until": paid_until,
        "grace_until": grace_until,
        "is_paid_active": is_paid_active,
        "is_grace_active": is_grace_active,
        "is_visible_now": is_visible_now,
    }


def public_visible_now(ad: Ad, subscription_visible_now: bool) -> bool:
    return bool(
        ad.status == "approved"
        and ad.is_active
        and ad.archived_at is None
        and subscription_visible_now
    )


def free_boost_reason(ad: Ad, subscription_visible_now: bool, now_utc: datetime) -> str | None:
    if ad.status != "approved":
        return f"status_{ad.status}"
    if not ad.is_active:
        return "inactive"
    if ad.archived_at is not None:
        return "archived"
    if not subscription_visible_now:
        return "subscription_inactive"
    if ad.last_free_boost_at is not None and msk_date(ad.last_free_boost_at) == msk_date(now_utc):
        return "already_used_today"
    return None


def build_cabinet_actions(ad: Ad, subscription_visible_now: bool, now_utc: datetime) -> CabinetActionFlags:
    boost_reason = free_boost_reason(ad, subscription_visible_now, now_utc)
    return CabinetActionFlags(
        can_edit=ad.archived_at is None,
        can_archive=ad.archived_at is None,
        can_unarchive=ad.archived_at is not None,
        can_upload_photos=ad.archived_at is None,
        can_free_boost=boost_reason is None,
        free_boost_reason=boost_reason,
    )


def effective_at_expr():
    return func.coalesce(Ad.boosted_at, Ad.created_at)


def msk_date(dt: datetime) -> datetime.date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK).date()


def build_storage_key(ad_id: UUID, photo_id: UUID, ext: str) -> str:
    return f"ads/{ad_id}/{photo_id}{ext}"


def local_uploads_root() -> Path:
    return Path("/app/static/uploads")


def ensure_local_path(storage_key: str) -> Path:
    root = local_uploads_root()
    path = root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def storage_path(storage_key: str) -> Path:
    return local_uploads_root() / storage_key


def build_public_url(storage_key: str) -> str:
    return f"/static/uploads/{storage_key}"


def guess_ext(content_type: str) -> str:
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    return ".jpg"


@router.post("", response_model=AdOut)
def create_ad(
    payload: AdCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    category = get_category_by_slug(db, payload.category_slug)
    if not category:
        raise api_error(404, "category_not_found", "Категория не найдена")

    city = get_city_by_slug(db, payload.city_slug)
    if not city:
        raise api_error(404, "city_not_found", "Город не найден")

    raw_phone = getattr(payload, "contact_phone", None)
    phone = normalize_ru_phone(raw_phone)
    if raw_phone and phone is None:
        raise api_error(422, "invalid_phone_format", "Неверный формат телефона")

    ad = Ad(
        master_id=user.id,
        category_id=category.id,
        city_id=city.id,
        title=payload.title,
        description=payload.description,
        price_from=payload.price_from,
        city=payload.city,
        status="moderation",
        work_time_text=getattr(payload, "work_time_text", None),
        contact_phone=phone,
        show_phone=getattr(payload, "show_phone", False),
        price_note=getattr(payload, "price_note", None),
    )

    districts = validate_and_fetch_districts(
        db,
        city.id,
        getattr(payload, "district_slugs", []) or [],
    )
    if districts:
        ad.districts_rel = districts

    db.add(ad)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise api_error(
            409,
            "ad_already_exists_in_category",
            "У вас уже есть объявление в этой категории",
        )

    ad = (
        db.query(Ad)
        .options(*ad_load_options())
        .filter(Ad.id == ad.id)
        .first()
    )

    return to_ad_out(ad)


@router.get("/my", response_model=list[AdOut])
def my_ads(
    status: str | None = Query(default=None, description="moderation|approved|blocked"),
    archived: bool | None = Query(default=None, description="true -> only archived, false -> only not archived"),
    category: str | None = Query(default=None, description="category slug"),
    city: str | None = Query(default=None, description="city slug"),
    is_active: bool | None = Query(default=None, description="filter by is_active"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    ads_query = (
        db.query(Ad)
        .options(*ad_load_options())
        .filter(Ad.master_id == user.id)
    )

    if status is not None:
        validate_status_filter(status)
        ads_query = ads_query.filter(Ad.status == status)

    if archived is True:
        ads_query = ads_query.filter(Ad.archived_at.is_not(None))
    elif archived is False:
        ads_query = ads_query.filter(Ad.archived_at.is_(None))

    if category:
        cat = get_category_by_slug(db, category)
        if not cat:
            return []
        ads_query = ads_query.filter(Ad.category_id == cat.id)

    if city:
        c = get_city_by_slug(db, city)
        if not c:
            return []
        ads_query = ads_query.filter(Ad.city_id == c.id)

    if is_active is not None:
        ads_query = ads_query.filter(Ad.is_active == is_active)

    ads = ads_query.order_by(Ad.created_at.desc()).all()
    return [to_ad_out(ad) for ad in ads]


@router.get("/my/stats", response_model=MyAdsStats)
def my_ads_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)
    return build_my_ads_stats(db, user.id)


@router.get("/my/cabinet", response_model=MasterCabinetOut)
def my_cabinet(
    status: str | None = Query(default=None, description="moderation|approved|blocked"),
    archived: bool | None = Query(default=None, description="true -> only archived, false -> only not archived"),
    category: str | None = Query(default=None, description="category slug"),
    city: str | None = Query(default=None, description="city slug"),
    is_active: bool | None = Query(default=None, description="filter by is_active"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)
    now_utc = datetime.now(timezone.utc)

    stats = build_my_ads_stats(db, user.id)

    subscription_rows = (
        db.query(Category, Subscription)
        .outerjoin(
            Subscription,
            (Subscription.master_id == user.id) & (Subscription.category_id == Category.id),
        )
        .order_by(Category.title.asc())
        .all()
    )

    categories_by_id: dict = {}
    subscriptions_by_category_id: dict = {}
    subscriptions_out: list[CabinetSubscriptionOut] = []

    for category_obj, subscription_obj in subscription_rows:
        categories_by_id[category_obj.id] = category_obj
        subscriptions_by_category_id[category_obj.id] = subscription_obj

        sub_flags = get_subscription_flags(subscription_obj, now_utc)

        subscriptions_out.append(
            CabinetSubscriptionOut(
                category_slug=category_obj.slug,
                category_title=category_obj.title,
                subscription_price=float(getattr(category_obj, "subscription_price", 0.0) or 0.0),
                has_subscription=sub_flags["has_subscription"],
                paid_until=sub_flags["paid_until"],
                grace_until=sub_flags["grace_until"],
                is_paid_active=sub_flags["is_paid_active"],
                is_grace_active=sub_flags["is_grace_active"],
                is_visible_now=sub_flags["is_visible_now"],
            )
        )

    ads_query = (
        db.query(Ad)
        .options(*ad_load_options())
        .filter(Ad.master_id == user.id)
    )

    empty_result = False

    if status is not None:
        validate_status_filter(status)
        ads_query = ads_query.filter(Ad.status == status)

    if archived is True:
        ads_query = ads_query.filter(Ad.archived_at.is_not(None))
    elif archived is False:
        ads_query = ads_query.filter(Ad.archived_at.is_(None))

    if category:
        cat = get_category_by_slug(db, category)
        if not cat:
            empty_result = True
        else:
            ads_query = ads_query.filter(Ad.category_id == cat.id)

    if city:
        c = get_city_by_slug(db, city)
        if not c:
            empty_result = True
        else:
            ads_query = ads_query.filter(Ad.city_id == c.id)

    if is_active is not None:
        ads_query = ads_query.filter(Ad.is_active == is_active)

    if empty_result:
        total = 0
        ads = []
    else:
        ads = (
            ads_query.order_by(effective_at_expr().desc(), Ad.created_at.desc(), Ad.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = ads_query.count()

    ads_out: list[CabinetAdItemOut] = []

    for ad in ads:
        category_obj = categories_by_id.get(ad.category_id)
        subscription_obj = subscriptions_by_category_id.get(ad.category_id)

        sub_flags = get_subscription_flags(subscription_obj, now_utc)
        subscription_visible = sub_flags["is_visible_now"]
        visible_now = public_visible_now(ad, subscription_visible)

        photos = list(getattr(ad, "photos", []) or [])
        districts = list(getattr(ad, "districts_rel", []) or [])

        actions = build_cabinet_actions(ad, subscription_visible, now_utc)

        ads_out.append(
            CabinetAdItemOut(
                id=ad.id,
                title=ad.title,
                description=ad.description,
                status=ad.status,
                is_active=ad.is_active,
                archived_at=ad.archived_at,
                blocked_reason=ad.blocked_reason,
                created_at=ad.created_at,
                boosted_at=ad.boosted_at,
                last_free_boost_at=ad.last_free_boost_at,
                category_slug=getattr(category_obj, "slug", ""),
                category_title=getattr(category_obj, "title", ""),
                city_slug=getattr(ad.city_rel, "slug", None) if getattr(ad, "city_rel", None) else None,
                city_title=getattr(ad.city_rel, "title", None) if getattr(ad, "city_rel", None) else None,
                district_slugs=[d.slug for d in districts],
                district_titles=[d.title for d in districts],
                cover_url=photos[0].url if photos else None,
                photos_count=len(photos),
                subscription_visible_now=subscription_visible,
                public_visible_now=visible_now,
                actions=actions,
            )
        )

    return MasterCabinetOut(
        master=CabinetMasterSummary(
            user_id=user.id,
            email=user.email,
            role=user.role,
            phone=getattr(user, "phone", None),
        ),
        stats=stats,
        subscriptions=subscriptions_out,
        total=total,
        limit=limit,
        offset=offset,
        ads=ads_out,
    )


@router.get("/my/{ad_id}", response_model=AdOwnerDetail)
def my_ad_detail(
    ad_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    ad = get_owned_ad(db, user.id, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    return to_ad_owner_detail(ad)


@router.patch("/{ad_id}", response_model=AdOut)
def update_my_ad(
    ad_id: UUID,
    payload: AdUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    ad = get_owned_ad(db, user.id, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    if payload.title is not None:
        ad.title = payload.title
    if payload.description is not None:
        ad.description = payload.description
    if payload.price_from is not None:
        ad.price_from = payload.price_from

    if getattr(payload, "city_slug", None) is not None:
        city = get_city_by_slug(db, payload.city_slug)
        if not city:
            raise api_error(404, "city_not_found", "Город не найден")
        ad.city_id = city.id

    if getattr(payload, "district_slugs", None) is not None:
        districts = validate_and_fetch_districts(db, ad.city_id, payload.district_slugs or [])
        ad.districts_rel = districts

    if getattr(payload, "city", None) is not None:
        ad.city = payload.city

    if getattr(payload, "work_time_text", None) is not None:
        ad.work_time_text = payload.work_time_text

    if getattr(payload, "contact_phone", None) is not None:
        raw_phone = payload.contact_phone
        phone = normalize_ru_phone(raw_phone)
        if raw_phone and phone is None:
            raise api_error(422, "invalid_phone_format", "Неверный формат телефона")
        ad.contact_phone = phone

    if getattr(payload, "show_phone", None) is not None:
        ad.show_phone = payload.show_phone

    if getattr(payload, "price_note", None) is not None:
        ad.price_note = payload.price_note

    if getattr(payload, "is_active", None) is not None:
        ad.is_active = payload.is_active

    ad.status = "moderation"
    db.commit()

    ad2 = (
        db.query(Ad)
        .options(*ad_load_options())
        .filter(Ad.id == ad.id)
        .first()
    )

    return to_ad_out(ad2)


@router.post("/{ad_id}/archive", response_model=AdOut)
def archive_my_ad(
    ad_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    ad = get_owned_ad(db, user.id, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    ad.archived_at = func.now()
    ad.is_active = False

    db.commit()
    db.refresh(ad)

    return to_ad_out(ad)


@router.post("/{ad_id}/unarchive", response_model=AdOut)
def unarchive_my_ad(
    ad_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    ad = get_owned_ad(db, user.id, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    ad.archived_at = None
    ad.is_active = True
    ad.status = "moderation"

    db.commit()
    db.refresh(ad)

    return to_ad_out(ad)


@router.post("/{ad_id}/free_boost", response_model=AdOut)
def free_boost_ad(
    ad_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)
    now_utc = datetime.now(timezone.utc)

    ad = get_owned_ad(db, user.id, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    if ad.status != "approved" or not ad.is_active or ad.archived_at is not None:
        raise api_error(
            409,
            "ad_not_ready_for_boost",
            "Объявление должно быть одобрено, активно и не в архиве",
        )

    sub = (
        db.query(Subscription)
        .filter(Subscription.master_id == ad.master_id, Subscription.category_id == ad.category_id)
        .first()
    )
    if not sub or sub.grace_until < now_utc:
        raise api_error(403, "subscription_inactive", "Подписка неактивна")

    if ad.last_free_boost_at is not None and msk_date(ad.last_free_boost_at) == msk_date(now_utc):
        raise api_error(
            409,
            "free_boost_already_used_today",
            "Бесплатный буст уже использован сегодня",
            {"timezone": "Europe/Moscow"},
        )

    ad.boosted_at = now_utc
    ad.last_free_boost_at = now_utc

    db.commit()
    db.refresh(ad)

    return to_ad_out(ad)


@router.post("/{ad_id}/photos", response_model=AdOut)
def upload_ad_photo(
    ad_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    ad = get_owned_ad(db, user.id, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise api_error(
            415,
            "unsupported_photo_type",
            "Неподдерживаемый тип файла",
            {
                "content_type": file.content_type,
                "allowed_types": sorted(ALLOWED_PHOTO_TYPES),
            },
        )

    content = file.file.read()
    max_bytes = MAX_PHOTO_SIZE_MB * 1024 * 1024

    if len(content) > max_bytes:
        raise api_error(
            413,
            "photo_too_large",
            f"Файл слишком большой, максимум {MAX_PHOTO_SIZE_MB} МБ",
            {"max_size_mb": MAX_PHOTO_SIZE_MB},
        )

    ext = guess_ext(file.content_type)
    photo_id = uuid.uuid4()
    storage_key = build_storage_key(ad_id, photo_id, ext)

    path = ensure_local_path(storage_key)
    with open(path, "wb") as f:
        f.write(content)

    current_max = max([p.sort_order for p in (ad.photos or [])] or [0])
    new_sort = current_max + 1

    photo = AdPhoto(
        id=photo_id,
        ad_id=ad.id,
        storage_key=storage_key,
        url=build_public_url(storage_key),
        sort_order=new_sort,
    )
    db.add(photo)

    if PHOTOS_TRIGGER_MODERATION:
        ad.status = "moderation"

    db.commit()

    ad2 = (
        db.query(Ad)
        .options(*ad_load_options())
        .filter(Ad.id == ad.id)
        .first()
    )

    return to_ad_out(ad2)


@router.delete("/{ad_id}/photos/{photo_id}", response_model=AdOut)
def delete_ad_photo(
    ad_id: UUID,
    photo_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    ad = get_owned_ad(db, user.id, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    photo = db.query(AdPhoto).filter(AdPhoto.id == photo_id, AdPhoto.ad_id == ad.id).first()
    if not photo:
        raise api_error(404, "photo_not_found", "Фото не найдено")

    path = storage_path(photo.storage_key)
    if path.exists():
        path.unlink(missing_ok=True)

    db.delete(photo)

    if PHOTOS_TRIGGER_MODERATION:
        ad.status = "moderation"

    db.commit()

    ad2 = (
        db.query(Ad)
        .options(*ad_load_options())
        .filter(Ad.id == ad.id)
        .first()
    )

    return to_ad_out(ad2)


@router.get("", response_model=list[AdOut])
def public_ads(
    category: str | None = Query(default=None, description="category slug"),
    city: str | None = Query(default=None, description="city slug"),
    district: str | None = Query(default=None, description="district slug(s), comma-separated (requires city)"),
    q: str | None = Query(default=None, description="search in title/description"),
    sort: str = Query(default="feed", description="feed|new|price_asc|price_desc|rating"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    ads_query = public_visible_query(db.query(Ad)).options(*ad_load_options())

    if category:
        cat = get_category_by_slug(db, category)
        if not cat:
            return []
        ads_query = ads_query.filter(Ad.category_id == cat.id)

    if district and not city:
        raise api_error(
            422,
            "district_requires_city",
            "Параметр district можно использовать только вместе с city",
        )

    if city:
        c = get_city_by_slug(db, city)
        if not c:
            return []
        ads_query = ads_query.filter(Ad.city_id == c.id)

        if district:
            slugs = [s.strip() for s in district.split(",") if s and s.strip()]
            slugs = list(dict.fromkeys(slugs))
            if slugs:
                ads_query = ads_query.filter(Ad.districts_rel.any(District.slug.in_(slugs)))

    if q:
        s = q.strip()
        if s:
            like = f"%{s}%"
            ads_query = ads_query.filter((Ad.title.ilike(like)) | (Ad.description.ilike(like)))

    eff = effective_at_expr()

    if sort in (None, "", "feed"):
        ads_query = ads_query.order_by(eff.desc(), Ad.created_at.desc(), Ad.id.desc())
    elif sort == "new":
        ads_query = ads_query.order_by(Ad.created_at.desc(), Ad.id.desc())
    elif sort == "price_asc":
        ads_query = ads_query.order_by(Ad.price_from.asc().nulls_last(), eff.desc(), Ad.id.desc())
    elif sort == "price_desc":
        ads_query = ads_query.order_by(Ad.price_from.desc().nulls_last(), eff.desc(), Ad.id.desc())
    elif sort == "rating":
        ads_query = ads_query.order_by(Ad.rating_avg.desc(), Ad.rating_count.desc(), eff.desc(), Ad.id.desc())
    else:
        raise api_error(
            422,
            "invalid_sort",
            "Недопустимый параметр сортировки",
            {"allowed": ["feed", "new", "price_asc", "price_desc", "rating"]},
        )

    ads = ads_query.offset(offset).limit(limit).all()
    return [to_ad_out(ad) for ad in ads]


@router.get("/{ad_id}", response_model=AdDetail)
def ad_detail(
    ad_id: UUID,
    db: Session = Depends(get_db),
):
    ad = get_public_ad(db, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    return to_ad_detail(ad)


@router.post("/{ad_id}/reveal_phone", response_model=RevealPhoneResponse)
def reveal_phone(
    ad_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ad = get_public_ad(db, ad_id)
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    if not getattr(ad, "show_phone", False):
        raise api_error(403, "phone_hidden", "Телефон скрыт")

    phone = getattr(ad, "contact_phone", None)
    if not phone:
        raise api_error(404, "phone_not_set", "Телефон не указан")

    return RevealPhoneResponse(phone=phone)
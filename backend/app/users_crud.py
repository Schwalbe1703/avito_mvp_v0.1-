from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.users_models import User


def get_user_by_email_or_phone(db: Session, email: str | None, phone: str | None) -> User | None:
    if not email and not phone:
        return None

    conditions = []
    if email:
        conditions.append(User.email == email)
    if phone:
        conditions.append(User.phone == phone)

    stmt = select(User).where(or_(*conditions))
    return db.execute(stmt).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    role: str,
    name: str,
    email: str | None,
    phone: str | None,
    password_hash: str,
) -> User:
    user = User(role=role, name=name, email=email, phone=phone, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id):
    return db.get(User, user_id)
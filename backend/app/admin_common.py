from fastapi import HTTPException


def require_admin(user):
    if getattr(user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
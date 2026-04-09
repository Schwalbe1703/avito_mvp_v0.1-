import uuid
import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.deps import get_db
from app.users_crud import create_user, get_user_by_email_or_phone

from app.categories_router import router as categories_router
from app.ads_router import router as ads_router
from app.admin_router import router as admin_router
from app.cities_router import router as cities_router
from app.districts_router import router as districts_router
from app.subscriptions_router import router as subscriptions_router
from app.reviews_router import router as reviews_router
from app.masters_router import router as masters_router
from app.clients_router import router as clients_router
from app.admin_reviews_router import router as admin_reviews_router
from app.admin_subscriptions_router import router as admin_subscriptions_router

def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]

    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://217.149.30.175",
        "http://217.149.30.175:3000",
        "http://217.149.30.175:5173",
    ]

app = FastAPI(docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

class RegisterIn(BaseModel):
    role: str  # client/master/admin
    name: str
    email: str | None = None
    phone: str | None = None
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    role: str
    name: str
    email: str | None
    phone: str | None


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/db-health")
def db_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"db": "ok"}


@app.post("/auth/register", response_model=UserOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if payload.role not in {"client", "master", "admin"}:
        raise HTTPException(status_code=400, detail="role must be client/master/admin")

    if not payload.email and not payload.phone:
        raise HTTPException(status_code=400, detail="email or phone is required")

    existing = get_user_by_email_or_phone(db, payload.email, payload.phone)
    if existing:
        raise HTTPException(status_code=409, detail="user already exists")

    user = create_user(
        db,
        role=payload.role,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    return UserOut(
        id=user.id,
        role=user.role,
        name=user.name,
        email=user.email,
        phone=user.phone,
    )


@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email_or_phone = form.username
    password = form.password

    if "@" in email_or_phone:
        email, phone = email_or_phone, None
    else:
        email, phone = None, email_or_phone

    user = get_user_by_email_or_phone(db, email, phone)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = create_access_token(str(user.id))
    return TokenOut(access_token=token)


@app.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return UserOut(
        id=user.id,
        role=user.role,
        name=user.name,
        email=user.email,
        phone=user.phone,
    )


# Routers
app.include_router(categories_router)
app.include_router(ads_router)
app.include_router(admin_router)
app.include_router(cities_router)
app.include_router(districts_router)
app.include_router(subscriptions_router)
app.include_router(reviews_router)
app.include_router(masters_router)
app.include_router(clients_router)
app.include_router(admin_reviews_router)
app.include_router(admin_subscriptions_router)


@app.get("/redoc", include_in_schema=False)
def redoc():
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>ReDoc</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>body{margin:0;padding:0}</style>
      </head>
      <body>
        <redoc spec-url="/openapi.json"></redoc>
        <script src="/static/redoc.standalone.js"></script>
      </body>
    </html>
    """
    return HTMLResponse(html)
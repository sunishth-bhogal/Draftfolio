"""Auth + profile endpoints. One team (portfolio) per user, created at signup."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Portfolio, User
from app.services import auth as auth_svc
from app.services import bootstrap
from app.services.rivals import xp_progress

router = APIRouter()

STARTING_CASH = Decimal("0")  # start empty; build capital via daily packs


class SignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=6, max_length=200)


class LoginRequest(BaseModel):
    login: str  # email or username
    password: str


class MeOut(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    xp: int
    level: int
    xp_into_level: int
    xp_per_level: int
    division: str
    division_points: int
    portfolio_id: str | None


class AuthOut(BaseModel):
    token: str
    user: MeOut


def _me(db: Session, user: User) -> MeOut:
    pf = db.scalar(select(Portfolio).where(Portfolio.user_id == user.id).limit(1))
    into, per = xp_progress(user.xp)
    return MeOut(
        id=str(user.id),
        username=user.username or user.display_name,
        display_name=user.display_name,
        email=user.email,
        xp=user.xp,
        level=user.level,
        xp_into_level=into,
        xp_per_level=per,
        division=user.division,
        division_points=user.division_points,
        portfolio_id=str(pf.id) if pf else None,
    )


@router.post("/auth/signup", response_model=AuthOut, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> AuthOut:
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=409, detail="email already registered")
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=409, detail="username taken")

    user = User(
        email=body.email,
        display_name=body.username,
        username=body.username,
        password_hash=auth_svc.hash_password(body.password),
    )
    db.add(user)
    db.commit()
    # One team per user.
    pf = bootstrap.create_portfolio(db, user_id=user.id, name=f"{body.username}'s Team")
    bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=STARTING_CASH, currency="CAD")
    return AuthOut(token=auth_svc.create_token(user.id), user=_me(db, user))


@router.post("/auth/login", response_model=AuthOut)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthOut:
    user = auth_svc.find_by_login(db, body.login)
    if user is None or not user.password_hash or not auth_svc.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    return AuthOut(token=auth_svc.create_token(user.id), user=_me(db, user))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(auth_svc.current_user), db: Session = Depends(get_db)) -> MeOut:
    return _me(db, user)

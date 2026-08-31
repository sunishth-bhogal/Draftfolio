"""Authentication — bcrypt password hashing + JWT sessions.

Standard, boring, correct: passwords are bcrypt-hashed (never stored or logged in
the clear), sessions are stateless JWTs signed with the app secret.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

ALGO = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=settings.token_ttl_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGO)


def _user_from_token(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGO])
    except jwt.PyJWTError:
        return None
    uid = payload.get("sub")
    if not uid:
        return None
    return db.get(User, uuid.UUID(uid))


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Require a valid Bearer token; raise 401 otherwise."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="not authenticated")
    user = _user_from_token(auth[7:], db)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return user


def find_by_login(db: Session, login: str) -> User | None:
    return db.scalar(
        select(User).where((User.email == login) | (User.username == login))
    )

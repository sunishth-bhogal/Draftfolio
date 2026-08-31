"""Auth flow tests."""

from __future__ import annotations


def test_signup_creates_user_and_team(client):
    r = client.post("/auth/signup", json={"email": "a@b.io", "username": "ace", "password": "secret1"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"]
    assert body["user"]["username"] == "ace"
    assert body["user"]["division"] == "Bronze"
    assert body["user"]["level"] == 1
    assert body["user"]["portfolio_id"]  # one team created


def test_login_and_me(client):
    client.post("/auth/signup", json={"email": "b@b.io", "username": "bee", "password": "secret1"})
    lg = client.post("/auth/login", json={"login": "bee", "password": "secret1"})
    assert lg.status_code == 200
    token = lg.json()["token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["username"] == "bee"


def test_login_by_email_too(client):
    client.post("/auth/signup", json={"email": "c@b.io", "username": "cat", "password": "secret1"})
    assert client.post("/auth/login", json={"login": "c@b.io", "password": "secret1"}).status_code == 200


def test_wrong_password_rejected(client):
    client.post("/auth/signup", json={"email": "d@b.io", "username": "dog", "password": "secret1"})
    assert client.post("/auth/login", json={"login": "dog", "password": "nope"}).status_code == 401


def test_me_requires_token(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_duplicate_email_and_username(client):
    client.post("/auth/signup", json={"email": "e@b.io", "username": "eel", "password": "secret1"})
    assert client.post("/auth/signup", json={"email": "e@b.io", "username": "x2", "password": "secret1"}).status_code == 409
    assert client.post("/auth/signup", json={"email": "z@b.io", "username": "eel", "password": "secret1"}).status_code == 409


def test_password_is_hashed_not_plaintext(client, db_session):
    from app.models import User
    from sqlalchemy import select

    client.post("/auth/signup", json={"email": "f@b.io", "username": "fox", "password": "secret1"})
    u = db_session.scalar(select(User).where(User.username == "fox"))
    assert u.password_hash and u.password_hash != "secret1" and u.password_hash.startswith("$2")

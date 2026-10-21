"""Signup / login with salted PBKDF2 password hashes and JWT bearer tokens."""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app import db

JWT_SECRET = os.getenv("JWT_SECRET") or "dev-only-secret-change-me-in-backend-env-file"
TOKEN_DAYS = 7

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(pw: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    check = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return hmac.compare_digest(check, digest)


def make_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, JWT_SECRET, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(401, "Not logged in")
    try:
        user_id = int(jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])["sub"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, please log in again")
    user = db.one("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
    if not user:
        raise HTTPException(401, "User not found")
    return user


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/signup")
def signup(body: SignupIn):
    email = body.email.strip().lower()
    if db.one("SELECT id FROM users WHERE email = ?", (email,)):
        raise HTTPException(409, "An account with this email already exists")
    uid = db.run("INSERT INTO users (name, email, pw_hash) VALUES (?, ?, ?)",
                 (body.name.strip(), email, hash_password(body.password)))
    return {"token": make_token(uid), "user": {"id": uid, "name": body.name.strip(), "email": email}}


@router.post("/login")
def login(body: LoginIn):
    user = db.one("SELECT * FROM users WHERE email = ?", (body.email.strip().lower(),))
    if not user or not verify_password(body.password, user["pw_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(user["id"]), "user": {"id": user["id"], "name": user["name"], "email": user["email"]}}

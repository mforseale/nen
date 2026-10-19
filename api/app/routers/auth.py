from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import AuthSession, User, UserCredential
from app.schemas import UserLogin, UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "nen_session"
SESSION_LIFETIME = timedelta(days=30)
PASSWORD_ITERATIONS = 310_000


def _hash_password(password: str, salt: bytes | None = None) -> str:
    password_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), password_salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${password_salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded_hash: str) -> bool:
    algorithm, iterations, salt_hex, digest_hex = encoded_hash.split("$", maxsplit=3)
    if algorithm != "pbkdf2_sha256":
        return False
    candidate_hash = _hash_password(password, bytes.fromhex(salt_hex)).split("$", maxsplit=3)[3]
    return hmac.compare_digest(candidate_hash, digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_session(user: User, db: Session, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(token),
            expires_at=expires_at,
        )
    )
    db.commit()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _token_hash(token))
    )
    if not auth_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid")

    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        db.delete(auth_session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")

    user = db.get(User, auth_session.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user no longer exists")
    return user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, response: Response, db: Session = Depends(get_db)):
    normalized_email = payload.email.strip().lower()
    normalized_username = payload.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{3,50}", normalized_username):
        raise HTTPException(422, "Логин: от 3 до 50 латинских букв, цифр или знаков подчёркивания")
    if len(payload.full_name.strip()) < 2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
        raise HTTPException(422, "Проверьте имя и адрес почты")
    existing_user = db.scalar(
        select(User).where(
            or_(User.email == normalized_email, User.username == normalized_username)
        )
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Эта почта или логин уже заняты.",
        )

    user = User(
        username=normalized_username,
        email=normalized_email,
        full_name=payload.full_name.strip(),
    )
    db.add(user)
    try:
        db.flush()
        db.add(UserCredential(user_id=user.id, password_hash=_hash_password(payload.password)))
        token = secrets.token_urlsafe(32)
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=_token_hash(token),
                expires_at=datetime.now(timezone.utc) + SESSION_LIFETIME,
            )
        )
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Эта почта или логин уже заняты.",
        ) from error

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
    )
    return user


@router.post("/login", response_model=UserRead)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    login_value = payload.login.strip()
    user = db.scalar(
        select(User).where(
            or_(User.username == login_value, User.email == login_value.lower())
        )
    )
    credential = db.get(UserCredential, user.id) if user else None
    if not user or not credential or not _verify_password(payload.password, credential.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин, почта или пароль.",
        )

    _issue_session(user, db, response)
    return user


@router.get("/me", response_model=UserRead)
def current_user(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        auth_session = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == _token_hash(token))
        )
        if auth_session:
            db.delete(auth_session)
            db.commit()
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response

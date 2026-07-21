"""
Lesson 29 - Authentication & Authorization
------------------------------------------
A runnable, database-backed auth API demonstrating the full stack:

    - password hashing with bcrypt (directly - NOT passlib, which is broken
      with modern bcrypt)
    - OAuth2 Password Flow login (OAuth2PasswordBearer + OAuth2PasswordRequestForm)
    - JWT access + refresh tokens with PyJWT
    - the get_current_user dependency (token -> user)
    - role-based access control via a require_role(...) dependency factory
    - API-key auth for machine-to-machine access

Install once:

    pip install fastapi uvicorn sqlalchemy pyjwt bcrypt python-multipart

How to run (from inside this folder):

    uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs and use the green "Authorize" button.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Body, Depends, FastAPI, HTTPException, Security, status
from fastapi.security import (
    APIKeyHeader,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

# ===========================================================================
# CONFIG - in a real app SECRET_KEY comes from env/config, never hardcoded.
# ===========================================================================
SECRET_KEY = "CHANGE-ME-32+bytes-of-random-in-real-life-0123456789abcdef"
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7
VALID_API_KEYS = {"service-key-abc123"}  # real apps store HASHED keys in the DB

DB_FILE = os.path.join(os.path.dirname(__file__), "auth.db")
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="user")  # "user" | "admin"
    disabled: Mapped[bool] = mapped_column(default=False)


# ===========================================================================
# PASSWORD HASHING - bcrypt directly (salted + slow, one-way)
# ===========================================================================
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ===========================================================================
# JWT - create + decode signed tokens (signed, NOT encrypted)
# ===========================================================================
def create_token(data: dict, token_type: str, expires: timedelta) -> str:
    payload = data.copy()
    payload["type"] = token_type
    payload["exp"] = datetime.now(timezone.utc) + expires
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(username: str, role: str) -> str:
    return create_token(
        {"sub": username, "role": role}, "access",
        timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )


def create_refresh_token(username: str) -> str:
    return create_token({"sub": username}, "refresh", timedelta(days=REFRESH_TOKEN_DAYS))


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # verifies sig + exp


# ===========================================================================
# DB dependency
# ===========================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


# ===========================================================================
# SCHEMAS
# ===========================================================================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=8, max_length=72)  # bcrypt hashes <= 72 bytes
    role: str = Field("user", pattern="^(user|admin)$")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    role: str
    disabled: bool


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ===========================================================================
# AUTHENTICATION dependencies
# ===========================================================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DB) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise CREDENTIALS_ERROR
        username = payload.get("sub")
        if username is None:
            raise CREDENTIALS_ERROR
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise CREDENTIALS_ERROR
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_user(current_user: CurrentUser) -> User:
    if current_user.disabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Inactive user")
    return current_user


ActiveUser = Annotated[User, Depends(get_current_active_user)]


# ===========================================================================
# AUTHORIZATION - RBAC dependency factory
# ===========================================================================
def require_role(*allowed_roles: str):
    def checker(current_user: ActiveUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Insufficient permissions"
            )
        return current_user

    return checker


# ===========================================================================
# API-KEY auth (machine-to-machine)
# ===========================================================================
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def require_api_key(key: Annotated[str, Security(api_key_header)]) -> str:
    if key not in VALID_API_KEYS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return key


# ===========================================================================
# APP
# ===========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Lesson 29 - Auth API", lifespan=lifespan)


@app.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DB):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),  # never store plaintext
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/token", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    user = db.scalar(select(User).where(User.username == form.username))
    # Same generic error whether the user is missing or the password is wrong.
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(user.username, user.role),
        refresh_token=create_refresh_token(user.username),
    )


@app.post("/refresh", response_model=Token)
def refresh(refresh_token: Annotated[str, Body(..., embed=True)], db: DB):
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":  # an access token cannot refresh
            raise CREDENTIALS_ERROR
        username = payload.get("sub")
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise CREDENTIALS_ERROR
    return Token(
        access_token=create_access_token(user.username, user.role),
        refresh_token=create_refresh_token(user.username),
    )


# ---- Protected (any authenticated, active user) ----
@app.get("/users/me", response_model=UserRead)
def read_me(current_user: ActiveUser):
    return current_user


# ---- Authorization: admin only ----
@app.get("/admin/users", response_model=list[UserRead])
def list_users(admin: Annotated[User, Depends(require_role("admin"))], db: DB):
    return db.scalars(select(User).order_by(User.id)).all()


@app.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, admin: Annotated[User, Depends(require_role("admin"))], db: DB
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    db.delete(user)
    db.commit()


# ---- API-key protected (machine-to-machine) ----
@app.get("/service/data")
def service_data(api_key: Annotated[str, Depends(require_api_key)]):
    return {"message": "authorized via API key", "data": [1, 2, 3]}

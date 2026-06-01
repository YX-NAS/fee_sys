from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import select
from typing import Annotated
from fastapi import Depends

from app.database import get_db
from app.dependencies import CurrentUser, DB
from app.models import User, UserStatus
from app.schemas import PasswordChange, RefreshRequest, TokenResponse, UserOut
from app.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DB,
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status != UserStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    payload = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: DB):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌"
    )
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exception
        user_id: str = payload["sub"]
    except (JWTError, KeyError):
        raise credentials_exception

    import uuid
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or user.status != UserStatus.active:
        raise credentials_exception

    p = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(p),
        refresh_token=create_refresh_token(p),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser):
    return current_user


@router.put("/me/password")
async def change_password(body: PasswordChange, current_user: CurrentUser, db: DB):
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    current_user.password_hash = hash_password(body.new_password)
    return {"message": "密码修改成功"}

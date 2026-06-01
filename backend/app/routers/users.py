import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DB, require_roles
from app.models import User, UserStatus
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("", response_model=dict)
async def list_users(
    db: DB,
    current_user: CurrentUser,
    _=require_roles("admin"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(User)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [UserOut.model_validate(u) for u in items]}


@router.post("", response_model=UserOut)
async def create_user(body: UserCreate, db: DB, current_user: CurrentUser, _=require_roles("admin")):
    exists = await db.execute(
        select(User).where((User.username == body.username) | (User.email == str(body.email)))
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在")
    user = User(
        username=body.username,
        email=str(body.email),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, db: DB, current_user: CurrentUser, _=require_roles("admin")
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        if k == "email":
            setattr(user, k, str(v))
        else:
            setattr(user, k, v)
    await db.flush()
    return UserOut.model_validate(user)

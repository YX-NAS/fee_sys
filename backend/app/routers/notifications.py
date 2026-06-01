import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from app.dependencies import CurrentUser, DB
from app.models import Notification
from app.schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["站内通知"])


@router.get("", response_model=dict)
async def list_notifications(
    db: DB,
    current_user: CurrentUser,
    is_read: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return {"total": total, "page": page, "page_size": page_size,
            "items": [NotificationOut.model_validate(n) for n in items]}


@router.get("/unread-count")
async def unread_count(db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(func.count()).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    )
    return {"count": result.scalar()}


@router.put("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(notification_id: uuid.UUID, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)
    await db.flush()
    return NotificationOut.model_validate(notif)


@router.put("/read-all")
async def mark_all_read(db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    )
    now = datetime.now(timezone.utc)
    for n in result.scalars().all():
        n.is_read = True
        n.read_at = now
    return {"message": "已全部标记为已读"}

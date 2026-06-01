import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DB
from app.models import Account, AlertConfig, AlertEvent, AlertEventStatus
from app.schemas import AlertConfigCreate, AlertConfigOut, AlertConfigUpdate, AlertEventOut
from app.security import encrypt_text

router = APIRouter(prefix="/api/alerts", tags=["提醒管理"])


# ── Alert Configs ─────────────────────────────────────────────────────────────

@router.get("/configs", response_model=dict)
async def list_alert_configs(
    db: DB,
    current_user: CurrentUser,
    account_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(AlertConfig)
    if account_id:
        query = query.where(AlertConfig.account_id == account_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(AlertConfig.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [AlertConfigOut.model_validate(c) for c in items]}


@router.post("/configs", response_model=AlertConfigOut, status_code=status.HTTP_201_CREATED)
async def create_alert_config(body: AlertConfigCreate, db: DB, current_user: CurrentUser):
    acc_result = await db.execute(
        select(Account).where(Account.id == body.account_id, Account.deleted_at.is_(None))
    )
    if acc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="账号不存在")

    data = body.model_dump(exclude={"webhook_url"})
    if body.webhook_url:
        data["webhook_url_encrypted"] = encrypt_text(body.webhook_url)

    cfg = AlertConfig(**data, created_by_id=current_user.id)
    db.add(cfg)
    await db.flush()
    return AlertConfigOut.model_validate(cfg)


@router.put("/configs/{config_id}", response_model=AlertConfigOut)
async def update_alert_config(config_id: uuid.UUID, body: AlertConfigUpdate, db: DB, current_user: CurrentUser):
    cfg = await _get_config_or_404(db, config_id)
    data = body.model_dump(exclude_none=True, exclude={"webhook_url"})
    if "webhook_url" in body.model_fields_set and body.webhook_url:
        data["webhook_url_encrypted"] = encrypt_text(body.webhook_url)
    for k, v in data.items():
        setattr(cfg, k, v)
    await db.flush()
    return AlertConfigOut.model_validate(cfg)


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_config(config_id: uuid.UUID, db: DB, current_user: CurrentUser):
    cfg = await _get_config_or_404(db, config_id)
    await db.delete(cfg)


# ── Alert Events ──────────────────────────────────────────────────────────────

@router.get("/events", response_model=dict)
async def list_alert_events(
    db: DB,
    current_user: CurrentUser,
    account_id: uuid.UUID | None = None,
    event_status: AlertEventStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    from app.models import AlertType
    query = select(AlertEvent)
    if account_id:
        query = query.where(AlertEvent.account_id == account_id)
    if event_status:
        query = query.where(AlertEvent.status == event_status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(AlertEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [AlertEventOut.model_validate(e) for e in items]}


@router.post("/events/{event_id}/acknowledge", response_model=AlertEventOut)
async def acknowledge_event(event_id: uuid.UUID, db: DB, current_user: CurrentUser):
    result = await db.execute(select(AlertEvent).where(AlertEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="提醒事件不存在")
    event.status = AlertEventStatus.acknowledged
    event.acknowledged_at = datetime.now(timezone.utc)
    event.acknowledged_by_id = current_user.id
    await db.flush()
    return AlertEventOut.model_validate(event)


@router.post("/events/{event_id}/retry", response_model=AlertEventOut)
async def retry_event(event_id: uuid.UUID, db: DB, current_user: CurrentUser):
    result = await db.execute(select(AlertEvent).where(AlertEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="提醒事件不存在")
    if event.status not in (AlertEventStatus.failed,):
        raise HTTPException(status_code=400, detail="只有失败状态的事件可以重试")

    cfg_result = await db.execute(select(AlertConfig).where(AlertConfig.id == event.config_id))
    cfg = cfg_result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=400, detail="关联提醒配置不存在")

    acc_result = await db.execute(select(Account).where(Account.id == event.account_id))
    acc = acc_result.scalar_one_or_none()

    from app.security import decrypt_text
    from app.services.notifications import dispatch_alert_event, _get_admin_ids
    webhook_url = None
    if cfg.webhook_url_encrypted:
        try:
            webhook_url = decrypt_text(cfg.webhook_url_encrypted)
        except Exception:
            pass

    admin_ids = await _get_admin_ids(db)
    await dispatch_alert_event(db, event, acc.name if acc else "未知账号",
                               cfg.webhook_type, webhook_url,
                               cfg.notify_inapp, cfg.notify_webhook, admin_ids)
    return AlertEventOut.model_validate(event)


async def _get_config_or_404(db, config_id: uuid.UUID) -> AlertConfig:
    result = await db.execute(select(AlertConfig).where(AlertConfig.id == config_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="提醒配置不存在")
    return cfg

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.ai_models import (
    AIAlertEvent, AIAlertRule, AIAlertType, AIBalanceSnapshot, AIDailyUsage,
    AIGatewayKey, AIGatewayKeyStatus, AIModelPrice, AIProviderAccount,
    AIProviderAPICredential, AISyncRun,
)
from app.ai_schemas import (
    AIAccountCreate, AIAccountOut, AIAccountUpdate, AIAlertEventOut,
    AIAlertRuleOut, AIAlertRuleUpsert, AIGatewayKeyCreate, AIGatewayKeyCreated,
    AIGatewayKeyOut, AIPriceCreate, AIPriceOut, AIProviderAPICredentialCreate,
    AIProviderAPICredentialOut, AIProviderAPICredentialUpdate, AISyncRequest,
    AITestConnectionOut,
)
from app.ai_schemas import _validate_provider_url
from app.config import get_settings
from app.dependencies import CurrentUser, DB, require_roles
from app.models import AlertEventStatus, User, UserRole
from app.security import encrypt_text
from app.services.ai.credentials import (
    api_credential_hint, validate_api_credentials,
)
from app.services.ai.monitoring import sync_account_balance, sync_account_usage, test_account_connection
from app.services.ai.providers import create_adapter
from app.services.ai.security import (
    decrypt_credentials, encrypt_credentials, generate_gateway_key, sanitize_provider_error,
)

router = APIRouter(prefix="/api/ai", tags=["AI 费用监控"])
settings = get_settings()
Admin = User


async def ai_viewer(current_user: CurrentUser) -> User:
    if settings.AI_MONITOR_ADMIN_ONLY and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="AI 费用监控正在管理员灰度阶段")
    return current_user


async def _account(db: DB, account_id: uuid.UUID) -> AIProviderAccount:
    item = (await db.execute(select(AIProviderAccount).where(AIProviderAccount.id == account_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="AI 厂商账号不存在")
    return item


async def _account_out(db: DB, item: AIProviderAccount) -> dict:
    count = (await db.execute(
        select(func.count(AIProviderAPICredential.id)).where(
            AIProviderAPICredential.provider_account_id == item.id,
            AIProviderAPICredential.is_active.is_(True),
        )
    )).scalar() or 0
    data = {column.name: getattr(item, column.name) for column in AIProviderAccount.__table__.columns}
    data["portal_credentials_configured"] = item.portal_credentials_configured
    data["api_credentials_configured"] = count > 0
    data["api_credentials_count"] = count
    return data


async def _api_credential(
    db: DB, account_id: uuid.UUID, credential_id: uuid.UUID,
) -> AIProviderAPICredential:
    item = (await db.execute(select(AIProviderAPICredential).where(
        AIProviderAPICredential.id == credential_id,
        AIProviderAPICredential.provider_account_id == account_id,
    ))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="官方 API 凭据不存在")
    return item


async def _make_default(db: DB, account_id: uuid.UUID, credential_id: uuid.UUID) -> None:
    rows = (await db.execute(select(AIProviderAPICredential).where(
        AIProviderAPICredential.provider_account_id == account_id,
    ))).scalars().all()
    for row in rows:
        row.is_default = row.id == credential_id


@router.get("/accounts", response_model=list[AIAccountOut])
async def list_accounts(db: DB, _: User = Depends(ai_viewer)):
    items = (await db.execute(
        select(AIProviderAccount).order_by(AIProviderAccount.created_at.desc())
    )).scalars().all()
    return [await _account_out(db, item) for item in items]


@router.post("/accounts", response_model=AIAccountOut, status_code=201)
async def create_account(body: AIAccountCreate, db: DB, user: User = Depends(require_roles("admin"))):
    try:
        _validate_provider_url(body.provider, body.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    portal_user = body.portal_username.strip() if body.portal_username else None
    portal_pass = body.portal_password.strip() if body.portal_password else None
    item = AIProviderAccount(
        **body.model_dump(exclude={"portal_username", "portal_password"}),
        portal_username_encrypted=encrypt_text(portal_user) if portal_user else None,
        portal_password_encrypted=encrypt_text(portal_pass) if portal_pass else None,
        created_by_id=user.id,
    )
    db.add(item)
    await db.flush()
    from app.ai_models import ai_default_severity_for
    for alert_type in AIAlertType:
        db.add(AIAlertRule(
            provider_account_id=item.id, alert_type=alert_type,
            severity=ai_default_severity_for(alert_type),
            failure_count=2,
            is_enabled=alert_type in (AIAlertType.balance_low, AIAlertType.sync_failed),
        ))
    await db.flush()
    return await _account_out(db, item)


@router.put("/accounts/{account_id}", response_model=AIAccountOut)
async def update_account(account_id: uuid.UUID, body: AIAccountUpdate, db: DB, _: User = Depends(require_roles("admin"))):
    item = await _account(db, account_id)
    try:
        _validate_provider_url(item.provider, body.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    values = body.model_dump(
        exclude_unset=True, exclude={"portal_username", "portal_password"}
    )
    for key, value in values.items():
        setattr(item, key, value)
    if body.portal_username is not None:
        if not body.portal_username.strip():
            raise HTTPException(status_code=422, detail="官网登录用户名不能为空")
        item.portal_username_encrypted = encrypt_text(body.portal_username)
    if body.portal_password is not None:
        if not body.portal_password:
            raise HTTPException(status_code=422, detail="官网登录密码不能为空")
        item.portal_password_encrypted = encrypt_text(body.portal_password)
    await db.flush()
    return await _account_out(db, item)


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: uuid.UUID, db: DB, _: User = Depends(require_roles("admin"))):
    await db.delete(await _account(db, account_id))


@router.post("/accounts/{account_id}/test", response_model=AITestConnectionOut)
async def test_account(account_id: uuid.UUID, db: DB, _: User = Depends(require_roles("admin"))):
    item = await _account(db, account_id)
    try:
        message, capabilities = await test_account_connection(db, item)
        return {"ok": True, "message": message, "capabilities": capabilities}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"连接失败: {sanitize_provider_error(exc)}") from None


@router.get(
    "/accounts/{account_id}/api-credentials",
    response_model=list[AIProviderAPICredentialOut],
)
async def list_api_credentials(
    account_id: uuid.UUID, db: DB, _: User = Depends(require_roles("admin")),
):
    await _account(db, account_id)
    return (await db.execute(select(AIProviderAPICredential).where(
        AIProviderAPICredential.provider_account_id == account_id,
    ).order_by(
        AIProviderAPICredential.is_default.desc(),
        AIProviderAPICredential.created_at.desc(),
    ))).scalars().all()


@router.post(
    "/accounts/{account_id}/api-credentials",
    response_model=AIProviderAPICredentialOut,
    status_code=201,
)
async def create_api_credential(
    account_id: uuid.UUID, body: AIProviderAPICredentialCreate, db: DB,
    user: User = Depends(require_roles("admin")),
):
    account = await _account(db, account_id)
    try:
        validate_api_credentials(account.provider, body.credential_type, body.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    existing_count = (await db.execute(select(func.count(AIProviderAPICredential.id)).where(
        AIProviderAPICredential.provider_account_id == account_id,
    ))).scalar() or 0
    item = AIProviderAPICredential(
        provider_account_id=account_id,
        name=body.name,
        credential_type=body.credential_type,
        credentials_encrypted=encrypt_credentials(body.credentials),
        key_hint=api_credential_hint(account.provider, body.credentials),
        is_default=body.is_default or existing_count == 0,
        created_by_id=user.id,
    )
    db.add(item)
    await db.flush()
    if item.is_default:
        await _make_default(db, account_id, item.id)
    await db.flush()
    return item


@router.put(
    "/accounts/{account_id}/api-credentials/{credential_id}",
    response_model=AIProviderAPICredentialOut,
)
async def update_api_credential(
    account_id: uuid.UUID, credential_id: uuid.UUID,
    body: AIProviderAPICredentialUpdate, db: DB,
    _: User = Depends(require_roles("admin")),
):
    account = await _account(db, account_id)
    item = await _api_credential(db, account_id, credential_id)
    if body.credentials is not None:
        try:
            validate_api_credentials(account.provider, item.credential_type, body.credentials)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        item.credentials_encrypted = encrypt_credentials(body.credentials)
        item.key_hint = api_credential_hint(account.provider, body.credentials)
    if body.name is not None:
        item.name = body.name
    if body.is_active is not None:
        item.is_active = body.is_active
        if not body.is_active:
            item.is_default = False
    if body.is_default:
        item.is_active = True
        await _make_default(db, account_id, item.id)
    await db.flush()
    return item


@router.delete("/accounts/{account_id}/api-credentials/{credential_id}", status_code=204)
async def delete_api_credential(
    account_id: uuid.UUID, credential_id: uuid.UUID, db: DB,
    _: User = Depends(require_roles("admin")),
):
    await db.delete(await _api_credential(db, account_id, credential_id))


@router.post(
    "/accounts/{account_id}/api-credentials/{credential_id}/test",
    response_model=AITestConnectionOut,
)
async def test_api_credential(
    account_id: uuid.UUID, credential_id: uuid.UUID, db: DB,
    _: User = Depends(require_roles("admin")),
):
    account = await _account(db, account_id)
    item = await _api_credential(db, account_id, credential_id)
    try:
        adapter = create_adapter(
            account.provider, decrypt_credentials(item.credentials_encrypted), account.base_url
        )
        message = await adapter.test_connection()
        item.last_tested_at = datetime.now(timezone.utc)
        item.last_test_status = "success"
        item.last_test_error = None
        await db.flush()
        return {"ok": True, "message": message, "capabilities": adapter.capabilities}
    except Exception as exc:
        message = sanitize_provider_error(exc)
        item.last_tested_at = datetime.now(timezone.utc)
        item.last_test_status = "failed"
        item.last_test_error = message
        await db.flush()
        raise HTTPException(status_code=400, detail=f"连接失败: {message}") from None


@router.post("/accounts/{account_id}/sync")
async def sync_account(account_id: uuid.UUID, body: AISyncRequest, db: DB, user: CurrentUser):
    if user.role == UserRole.viewer or (settings.AI_MONITOR_ADMIN_ONLY and user.role != UserRole.admin):
        raise HTTPException(status_code=403, detail="权限不足")
    item = await _account(db, account_id)
    run = await sync_account_usage(db, item, body.start_date, body.end_date)
    await db.commit()
    return {"id": run.id, "status": run.status, "records_processed": run.records_processed, "error": run.error_message}


@router.post("/accounts/{account_id}/sync-balance")
async def sync_balance(account_id: uuid.UUID, db: DB, user: CurrentUser):
    if user.role == UserRole.viewer or (settings.AI_MONITOR_ADMIN_ONLY and user.role != UserRole.admin):
        raise HTTPException(status_code=403, detail="权限不足")
    snapshot = await sync_account_balance(db, await _account(db, account_id))
    await db.commit()
    return {"available_balance": snapshot.available_balance, "currency": snapshot.currency}


@router.get("/accounts/{account_id}/gateway-keys", response_model=list[AIGatewayKeyOut])
async def list_gateway_keys(account_id: uuid.UUID, db: DB, _: User = Depends(require_roles("admin"))):
    return (await db.execute(select(AIGatewayKey).where(AIGatewayKey.provider_account_id == account_id).order_by(AIGatewayKey.created_at.desc()))).scalars().all()


@router.post("/accounts/{account_id}/gateway-keys", response_model=AIGatewayKeyCreated, status_code=201)
async def create_gateway_key(account_id: uuid.UUID, body: AIGatewayKeyCreate, db: DB, user: User = Depends(require_roles("admin"))):
    account = await _account(db, account_id)
    if account.provider.value != "deepseek":
        raise HTTPException(status_code=400, detail="仅 DeepSeek 账号支持网关 Key")
    plaintext, prefix, digest = generate_gateway_key()
    item = AIGatewayKey(
        provider_account_id=account.id, name=body.name, key_prefix=prefix,
        key_hash=digest, rate_limit_per_minute=body.rate_limit_per_minute,
        expires_at=body.expires_at, created_by_id=user.id,
    )
    db.add(item)
    await db.flush()
    return AIGatewayKeyCreated(**AIGatewayKeyOut.model_validate(item).model_dump(), key=plaintext)


@router.post("/gateway-keys/{key_id}/disable", response_model=AIGatewayKeyOut)
async def disable_gateway_key(key_id: uuid.UUID, db: DB, _: User = Depends(require_roles("admin"))):
    item = (await db.execute(select(AIGatewayKey).where(AIGatewayKey.id == key_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="网关 Key 不存在")
    item.status = AIGatewayKeyStatus.disabled
    await db.flush()
    return item


@router.get("/overview")
async def overview(db: DB, _: User = Depends(ai_viewer)):
    today = datetime.now().date()
    month_start = today.replace(day=1)
    async def total(start: date, end: date):
        return (await db.execute(
            select(func.coalesce(func.sum(func.coalesce(AIDailyUsage.provider_reported_cost, AIDailyUsage.calculated_cost)), 0))
            .where(AIDailyUsage.usage_date.between(start, end))
        )).scalar()
    accounts = (await db.execute(select(func.count(AIProviderAccount.id)))).scalar()
    errors = (await db.execute(select(func.count(AIProviderAccount.id)).where(AIProviderAccount.consecutive_failures > 0))).scalar()
    balance_rows = await db.execute(
        select(AIBalanceSnapshot.provider_account_id, func.max(AIBalanceSnapshot.snapshot_time))
        .group_by(AIBalanceSnapshot.provider_account_id)
    )
    balances = []
    for account_id, stamp in balance_rows.all():
        snap = (await db.execute(select(AIBalanceSnapshot).where(
            AIBalanceSnapshot.provider_account_id == account_id,
            AIBalanceSnapshot.snapshot_time == stamp,
        ))).scalar_one()
        balances.append({"account_id": account_id, "balance": snap.available_balance, "currency": snap.currency})
    return {
        "today_cost": await total(today, today),
        "yesterday_cost": await total(today - timedelta(days=1), today - timedelta(days=1)),
        "month_cost": await total(month_start, today),
        "account_count": accounts, "abnormal_account_count": errors, "balances": balances,
    }


@router.get("/usage/daily")
async def daily_usage(
    db: DB, _: User = Depends(ai_viewer), start_date: date = Query(...),
    end_date: date = Query(...), account_id: uuid.UUID | None = None,
):
    query = select(AIDailyUsage).where(AIDailyUsage.usage_date.between(start_date, end_date))
    if account_id:
        query = query.where(AIDailyUsage.provider_account_id == account_id)
    rows = (await db.execute(query.order_by(AIDailyUsage.usage_date))).scalars().all()
    return [{"id": r.id, "account_id": r.provider_account_id, "date": r.usage_date, "model": r.model,
             "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
             "cached_input_tokens": r.cached_input_tokens, "reasoning_tokens": r.reasoning_tokens,
             "request_count": r.request_count, "actual_cost": r.provider_reported_cost,
             "calculated_cost": r.calculated_cost, "cost_source": r.cost_source, "currency": r.currency} for r in rows]


@router.get("/models")
async def model_ranking(db: DB, _: User = Depends(ai_viewer), start_date: date = Query(...), end_date: date = Query(...)):
    rows = await db.execute(
        select(AIDailyUsage.model, func.sum(AIDailyUsage.request_count),
               func.sum(AIDailyUsage.input_tokens + AIDailyUsage.output_tokens),
               func.sum(func.coalesce(AIDailyUsage.provider_reported_cost, AIDailyUsage.calculated_cost)))
        .where(AIDailyUsage.usage_date.between(start_date, end_date))
        .group_by(AIDailyUsage.model).order_by(func.sum(AIDailyUsage.calculated_cost).desc())
    )
    return [{"model": r[0], "request_count": r[1], "total_tokens": r[2], "cost": r[3]} for r in rows.all()]


@router.get("/balances")
async def balances(db: DB, _: User = Depends(ai_viewer), account_id: uuid.UUID | None = None, limit: int = Query(100, le=500)):
    query = select(AIBalanceSnapshot)
    if account_id:
        query = query.where(AIBalanceSnapshot.provider_account_id == account_id)
    rows = (await db.execute(query.order_by(AIBalanceSnapshot.snapshot_time.desc()).limit(limit))).scalars().all()
    return [{"account_id": r.provider_account_id, "balance": r.available_balance, "currency": r.currency, "snapshot_time": r.snapshot_time} for r in rows]


@router.get("/sync-runs")
async def sync_runs(db: DB, _: User = Depends(ai_viewer), limit: int = Query(100, le=500)):
    rows = (await db.execute(select(AISyncRun).order_by(AISyncRun.started_at.desc()).limit(limit))).scalars().all()
    return [{"id": r.id, "account_id": r.provider_account_id, "sync_type": r.sync_type,
             "start_date": r.start_date, "end_date": r.end_date, "status": r.status,
             "records_processed": r.records_processed, "error": r.error_message,
             "started_at": r.started_at, "finished_at": r.finished_at} for r in rows]


@router.get("/prices", response_model=list[AIPriceOut])
async def prices(db: DB, _: User = Depends(ai_viewer)):
    return (await db.execute(select(AIModelPrice).order_by(AIModelPrice.provider, AIModelPrice.model, AIModelPrice.effective_from.desc()))).scalars().all()


@router.post("/prices", response_model=AIPriceOut, status_code=201)
async def create_price(body: AIPriceCreate, db: DB, user: User = Depends(require_roles("admin"))):
    overlap = (await db.execute(select(AIModelPrice.id).where(
        AIModelPrice.provider == body.provider,
        AIModelPrice.model == body.model,
        AIModelPrice.effective_from <= (body.effective_to or date.max),
        (AIModelPrice.effective_to.is_(None) | (AIModelPrice.effective_to >= body.effective_from)),
    ).limit(1))).scalar_one_or_none()
    if overlap:
        raise HTTPException(status_code=409, detail="该模型价格有效期与已有版本重叠")
    item = AIModelPrice(**body.model_dump(), created_by_id=user.id)
    db.add(item)
    await db.flush()
    return item


@router.get("/alerts")
async def alerts(db: DB, _: User = Depends(ai_viewer)):
    rules = (await db.execute(select(AIAlertRule).order_by(AIAlertRule.created_at))).scalars().all()
    events = (await db.execute(select(AIAlertEvent).order_by(AIAlertEvent.created_at.desc()).limit(100))).scalars().all()
    return {"rules": [AIAlertRuleOut.model_validate(r) for r in rules], "events": [AIAlertEventOut.model_validate(e) for e in events]}


@router.put("/accounts/{account_id}/alerts/{alert_type}", response_model=AIAlertRuleOut)
async def update_alert(account_id: uuid.UUID, alert_type: str, body: AIAlertRuleUpsert, db: DB, _: User = Depends(require_roles("admin"))):
    if body.alert_type.value != alert_type:
        raise HTTPException(status_code=400, detail="告警类型不一致")
    rule = (await db.execute(select(AIAlertRule).where(
        AIAlertRule.provider_account_id == account_id, AIAlertRule.alert_type == body.alert_type,
    ))).scalar_one_or_none()
    if not rule:
        from app.ai_models import ai_default_severity_for
        rule = AIAlertRule(
            provider_account_id=account_id, alert_type=body.alert_type,
            severity=body.severity or ai_default_severity_for(body.alert_type),
        )
        db.add(rule)
    values = body.model_dump(exclude={"webhook_url"})
    if values.get("severity") is None:
        values.pop("severity", None)
    for key, value in values.items():
        setattr(rule, key, value)
    if body.webhook_url:
        rule.webhook_url_encrypted = encrypt_text(body.webhook_url)
    await db.flush()
    return rule


@router.post("/alerts/{event_id}/acknowledge", response_model=AIAlertEventOut)
async def acknowledge_alert(event_id: uuid.UUID, db: DB, user: CurrentUser):
    event = (await db.execute(select(AIAlertEvent).where(AIAlertEvent.id == event_id))).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="告警事件不存在")
    event.status = AlertEventStatus.acknowledged
    event.acknowledged_at = datetime.now(timezone.utc)
    event.acknowledged_by_id = user.id
    await db.flush()
    return event

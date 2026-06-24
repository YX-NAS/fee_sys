import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_models import (
    AIAccountStatus, AIAlertEvent, AIAlertRule, AIAlertType, AIBalanceSnapshot,
    AICostSource, AIDailyUsage, AIGatewayRequest, AIModelPrice, AIProvider,
    AIProviderAccount, AIRequestStatus, AISyncRun, AISyncStatus,
    ai_default_severity_for,
)
from app.models import (
    AlertEventStatus, ChannelStatus, Notification, User, UserRole, UserStatus,
)
from app.services.ai.pricing import calculate_token_cost
from app.services.ai.providers import create_adapter
from app.services.ai.credentials import load_default_api_credentials
from app.security import decrypt_text
from app.services.ai.security import sanitize_provider_error

logger = logging.getLogger(__name__)


async def get_effective_price(
    db: AsyncSession, provider: AIProvider, model: str, usage_date: date,
) -> AIModelPrice | None:
    result = await db.execute(
        select(AIModelPrice)
        .where(
            AIModelPrice.provider == provider,
            AIModelPrice.model == model,
            AIModelPrice.effective_from <= usage_date,
            or_(AIModelPrice.effective_to.is_(None), AIModelPrice.effective_to >= usage_date),
        )
        .order_by(AIModelPrice.effective_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def record_gateway_request(
    db: AsyncSession,
    *,
    account: AIProviderAccount,
    gateway_key_id: uuid.UUID,
    model: str,
    endpoint: str,
    usage: dict[str, int],
    request_status: AIRequestStatus,
    http_status: int | None,
    duration_ms: int,
    provider_request_id: str | None = None,
    error_code: str | None = None,
) -> AIGatewayRequest:
    today = datetime.now(timezone.utc).astimezone(ZoneInfo(account.timezone)).date()
    price = await get_effective_price(db, account.provider, model, today)
    cost = calculate_token_cost(usage, price)
    request = AIGatewayRequest(
        provider_account_id=account.id,
        gateway_key_id=gateway_key_id,
        provider_request_id=provider_request_id,
        model=model,
        endpoint=endpoint,
        status=request_status,
        http_status=http_status,
        duration_ms=duration_ms,
        error_code=error_code,
        usage_date=today,
        calculated_cost=cost,
        currency=price.currency if price else account.currency,
        **usage,
    )
    db.add(request)
    if request_status == AIRequestStatus.success:
        values = {
            "id": uuid.uuid4(),
            "provider_account_id": account.id,
            "usage_date": today,
            "model": model,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cached_input_tokens": usage["cached_input_tokens"],
            "reasoning_tokens": usage["reasoning_tokens"],
            "request_count": 1,
            "provider_reported_cost": None,
            "calculated_cost": cost,
            "currency": price.currency if price else account.currency,
            "cost_source": AICostSource.calculated,
            "synced_at": datetime.now(timezone.utc),
        }
        stmt = insert(AIDailyUsage).values(**values)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ai_daily_account_date_model",
            set_={
                "input_tokens": AIDailyUsage.input_tokens + excluded.input_tokens,
                "output_tokens": AIDailyUsage.output_tokens + excluded.output_tokens,
                "cached_input_tokens": AIDailyUsage.cached_input_tokens + excluded.cached_input_tokens,
                "reasoning_tokens": AIDailyUsage.reasoning_tokens + excluded.reasoning_tokens,
                "request_count": AIDailyUsage.request_count + 1,
                "calculated_cost": AIDailyUsage.calculated_cost + excluded.calculated_cost,
                "currency": excluded.currency,
                "synced_at": excluded.synced_at,
            },
        )
        await db.execute(stmt)
    await db.flush()
    return request


async def test_account_connection(
    db: AsyncSession, account: AIProviderAccount,
) -> tuple[str, dict[str, bool]]:
    adapter = create_adapter(account.provider, await load_default_api_credentials(db, account), account.base_url)
    return await adapter.test_connection(), adapter.capabilities


async def sync_account_balance(db: AsyncSession, account: AIProviderAccount) -> AIBalanceSnapshot:
    run = AISyncRun(provider_account_id=account.id, sync_type="balance", status=AISyncStatus.running)
    db.add(run)
    await db.flush()
    try:
        adapter = create_adapter(
            account.provider, await load_default_api_credentials(db, account), account.base_url
        )
        value = await adapter.fetch_balance()
        snapshot = AIBalanceSnapshot(provider_account_id=account.id, **value)
        db.add(snapshot)
        account.last_sync_at = datetime.now(timezone.utc)
        account.last_sync_status = AISyncStatus.success
        account.last_sync_error = None
        account.consecutive_failures = 0
        account.status = AIAccountStatus.active
        run.status = AISyncStatus.success
        run.records_processed = 1
        await db.flush()
        await evaluate_ai_alerts(db, account, balance=snapshot.available_balance)
        return snapshot
    except Exception as exc:
        message = sanitize_provider_error(exc)
        account.last_sync_at = datetime.now(timezone.utc)
        account.last_sync_status = AISyncStatus.failed
        account.last_sync_error = message
        account.consecutive_failures += 1
        account.status = AIAccountStatus.error
        run.status = AISyncStatus.failed
        run.error_message = message
        await db.flush()
        await evaluate_ai_alerts(db, account)
        raise
    finally:
        run.finished_at = datetime.now(timezone.utc)


async def sync_account_usage(
    db: AsyncSession, account: AIProviderAccount, start_date: date, end_date: date,
) -> AISyncRun:
    run = AISyncRun(
        provider_account_id=account.id, sync_type="usage",
        start_date=start_date, end_date=end_date, status=AISyncStatus.running,
    )
    db.add(run)
    await db.flush()
    try:
        adapter = create_adapter(
            account.provider, await load_default_api_credentials(db, account), account.base_url
        )
        rows = await adapter.fetch_usage(start_date, end_date)
        costs = await adapter.fetch_cost(start_date, end_date)
        cost_map = {(r["usage_date"], r["model"]): r for r in costs}
        bill_dates = {r["usage_date"] for r in costs}
        consumed_cost_keys: set[tuple[date, str]] = set()
        for row in rows:
            actual = cost_map.get((row["usage_date"], row["model"]))
            if actual:
                consumed_cost_keys.add((row["usage_date"], row["model"]))
            price = await get_effective_price(db, account.provider, row["model"], row["usage_date"])
            calculated = Decimal("0") if row["usage_date"] in bill_dates else calculate_token_cost(row, price)
            values = {
                "id": uuid.uuid4(), "provider_account_id": account.id,
                "usage_date": row["usage_date"], "model": row["model"],
                "input_tokens": row.get("input_tokens", 0),
                "output_tokens": row.get("output_tokens", 0),
                "cached_input_tokens": row.get("cached_input_tokens", 0),
                "reasoning_tokens": row.get("reasoning_tokens", 0),
                "request_count": row.get("request_count", 0),
                "provider_reported_cost": actual["cost"] if actual else None,
                "calculated_cost": calculated,
                "currency": actual.get("currency", account.currency) if actual else (price.currency if price else account.currency),
                "cost_source": AICostSource.provider if actual else AICostSource.calculated,
                "synced_at": datetime.now(timezone.utc),
            }
            stmt = insert(AIDailyUsage).values(**values).on_conflict_do_update(
                constraint="uq_ai_daily_account_date_model",
                set_={k: v for k, v in values.items() if k not in {"id", "provider_account_id", "usage_date", "model"}},
            )
            await db.execute(stmt)
        for cost in costs:
            key = (cost["usage_date"], cost["model"])
            if key in consumed_cost_keys:
                continue
            values = {
                "id": uuid.uuid4(), "provider_account_id": account.id,
                "usage_date": cost["usage_date"], "model": f"{cost['model']} (账单)",
                "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0,
                "reasoning_tokens": 0, "request_count": 0,
                "provider_reported_cost": cost["cost"], "calculated_cost": Decimal("0"),
                "currency": cost["currency"], "cost_source": AICostSource.provider,
                "synced_at": datetime.now(timezone.utc),
            }
            await db.execute(insert(AIDailyUsage).values(**values).on_conflict_do_update(
                constraint="uq_ai_daily_account_date_model",
                set_={k: v for k, v in values.items() if k not in {"id", "provider_account_id", "usage_date", "model"}},
            ))
        run.records_processed = len(rows) + len(costs)
        run.status = AISyncStatus.success
        account.last_sync_status = AISyncStatus.success
        account.last_sync_error = None
        account.consecutive_failures = 0
        account.status = AIAccountStatus.active
        await db.flush()
        # 用量同步成功后也评估 cost_spike / no_usage 告警
        await evaluate_ai_alerts(db, account, sync_type="usage")
    except Exception as exc:
        message = sanitize_provider_error(exc)
        run.status = AISyncStatus.failed
        run.error_message = message
        account.last_sync_status = AISyncStatus.failed
        account.last_sync_error = message
        account.consecutive_failures += 1
        account.status = AIAccountStatus.error
        await evaluate_ai_alerts(db, account)
    finally:
        now = datetime.now(timezone.utc)
        run.finished_at = now
        account.last_sync_at = now
        await db.flush()
    return run


async def rebuild_gateway_daily(db: AsyncSession, usage_date: date) -> int:
    account_ids = (
        await db.execute(select(AIProviderAccount.id).where(AIProviderAccount.provider.in_([AIProvider.deepseek, AIProvider.kimi])))
    ).scalars().all()
    count = 0
    for account_id in account_ids:
        await db.execute(
            AIDailyUsage.__table__.delete().where(
                AIDailyUsage.provider_account_id == account_id,
                AIDailyUsage.usage_date == usage_date,
            )
        )
        rows = await db.execute(
            select(
                AIGatewayRequest.model,
                func.sum(AIGatewayRequest.input_tokens),
                func.sum(AIGatewayRequest.output_tokens),
                func.sum(AIGatewayRequest.cached_input_tokens),
                func.sum(AIGatewayRequest.reasoning_tokens),
                func.count(AIGatewayRequest.id),
                func.sum(AIGatewayRequest.calculated_cost),
                func.max(AIGatewayRequest.currency),
            )
            .where(
                AIGatewayRequest.provider_account_id == account_id,
                AIGatewayRequest.usage_date == usage_date,
                AIGatewayRequest.status == AIRequestStatus.success,
            )
            .group_by(AIGatewayRequest.model)
        )
        for row in rows.all():
            db.add(AIDailyUsage(
                provider_account_id=account_id, usage_date=usage_date, model=row[0],
                input_tokens=row[1] or 0, output_tokens=row[2] or 0,
                cached_input_tokens=row[3] or 0, reasoning_tokens=row[4] or 0,
                request_count=row[5] or 0, calculated_cost=row[6] or Decimal("0"),
                currency=row[7] or "CNY", cost_source=AICostSource.calculated,
            ))
            count += 1
    await db.flush()
    return count


async def evaluate_ai_alerts(
    db: AsyncSession, account: AIProviderAccount,
    balance: Decimal | None = None, sync_type: str | None = None,
) -> None:
    """评估 AI 账号的告警规则。

    sync_type="usage" 时只评估 cost_spike / no_usage；
    balance 传入时评估全部规则；两者均无时只评估 sync_failed。
    """
    rules = (
        await db.execute(
            select(AIAlertRule).where(
                AIAlertRule.provider_account_id == account.id,
                AIAlertRule.is_enabled.is_(True),
            )
        )
    ).scalars().all()
    if not rules:
        return
    now = datetime.now(timezone.utc)
    admin_ids = (
        await db.execute(
            select(User.id).where(
                User.status == UserStatus.active,
                User.role.in_([UserRole.admin, UserRole.operator]),
            )
        )
    ).scalars().all()

    for rule in rules:
        if rule.last_triggered_at and now - rule.last_triggered_at < timedelta(hours=rule.cooldown_hours):
            continue

        # 决定是否评估该规则
        if sync_type == "usage" and rule.alert_type not in (AIAlertType.cost_spike, AIAlertType.no_usage):
            continue

        triggered = False
        value: Decimal | None = None
        message = ""

        if rule.alert_type == AIAlertType.balance_low and balance is not None and rule.threshold_amount is not None:
            triggered = balance < rule.threshold_amount
            value = balance
            message = f"AI 账号【{account.name}】余额 {balance} 低于阈值 {rule.threshold_amount}"
        elif rule.alert_type == AIAlertType.sync_failed:
            triggered = account.consecutive_failures >= rule.failure_count
            value = Decimal(account.consecutive_failures)
            message = f"AI 账号【{account.name}】已连续同步失败 {account.consecutive_failures} 次"
        elif rule.alert_type == AIAlertType.cost_spike and rule.threshold_amount is not None:
            today = datetime.now().date()
            week_ago = today - timedelta(days=7)

            async def _cost_since(start):
                r = await db.execute(
                    select(func.coalesce(func.sum(func.coalesce(AIDailyUsage.provider_reported_cost, AIDailyUsage.calculated_cost)), 0))
                    .where(AIDailyUsage.provider_account_id == account.id, AIDailyUsage.usage_date >= start)
                )
                return r.scalar() or Decimal("0")

            today_cost = await _cost_since(today)
            week_total = await _cost_since(week_ago)
            # 上周总消费为 0 时不触发突增告警（没有基线可比）
            if week_total > 0:
                avg = week_total / Decimal("7")
                triggered = today_cost > avg * rule.threshold_amount
            else:
                triggered = False
            value = today_cost
            message = f"AI 账号【{account.name}】今日费用 {today_cost} 超过近 7 日日均的 {rule.threshold_amount} 倍"
        elif rule.alert_type == AIAlertType.no_usage:
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            count = (await db.execute(
                select(func.count(AIDailyUsage.id)).where(
                    AIDailyUsage.provider_account_id == account.id,
                    AIDailyUsage.usage_date.in_([yesterday, today]),
                )
            )).scalar() or 0
            triggered = count == 0
            value = Decimal("0")
            message = f"AI 账号【{account.name}】昨日及今日均无用量数据"

        if not triggered:
            continue

        severity = rule.severity or ai_default_severity_for(rule.alert_type)
        event = AIAlertEvent(
            rule_id=rule.id, provider_account_id=account.id, alert_type=rule.alert_type,
            severity=severity, triggered_value=value, threshold_value=rule.threshold_amount,
            message=message, status=AlertEventStatus.pending,
            inapp_status=ChannelStatus.pending if rule.notify_inapp else ChannelStatus.skipped,
            webhook_status=ChannelStatus.pending if rule.notify_webhook else ChannelStatus.skipped,
        )
        db.add(event)
        await db.flush()

        webhook_url = None
        if rule.notify_webhook and rule.webhook_url_encrypted and rule.webhook_type:
            try:
                webhook_url = decrypt_text(rule.webhook_url_encrypted)
            except Exception:
                logger.warning("AI 告警 webhook URL 解密失败, rule_id=%s", rule.id)

        await _dispatch_ai_alert_event(
            db, event, account.name, rule.webhook_type, webhook_url,
            rule.notify_inapp, rule.notify_webhook, admin_ids, severity,
        )
        rule.last_triggered_at = now
        logger.info("AI 告警触发, account_id=%s type=%s severity=%s", account.id, rule.alert_type, severity)


async def _dispatch_ai_alert_event(
    db: AsyncSession, event: AIAlertEvent, account_name: str,
    webhook_type: str | None, webhook_url: str | None,
    notify_inapp: bool, notify_webhook: bool,
    admin_ids: list, severity,
) -> None:
    """分发一条 AI 告警事件到启用的通道，并设置状态。"""
    title = f"[{severity.value.upper()}] AI 费用监控告警 - {account_name}"
    if notify_inapp:
        try:
            for uid in admin_ids:
                db.add(Notification(user_id=uid, title=title, content=event.message))
            await db.flush()
            event.inapp_status = ChannelStatus.sent
        except Exception:
            logger.exception("AI 告警站内通知创建失败, event_id=%s", event.id)
            event.inapp_status = ChannelStatus.failed
    else:
        event.inapp_status = ChannelStatus.skipped

    if notify_webhook and webhook_url and webhook_type:
        try:
            await _send_ai_webhook(webhook_type, webhook_url, f"{title}\n{event.message}")
            event.webhook_status = ChannelStatus.sent
        except Exception:
            logger.exception("AI 告警 webhook 发送失败, event_id=%s", event.id)
            event.webhook_status = ChannelStatus.failed
    else:
        event.webhook_status = ChannelStatus.skipped

    if (event.inapp_status in (ChannelStatus.sent, ChannelStatus.skipped) and
            event.webhook_status in (ChannelStatus.sent, ChannelStatus.skipped)):
        event.status = AlertEventStatus.sent
    else:
        event.status = AlertEventStatus.failed
        event.retry_count += 1
        event.last_retry_at = datetime.now(timezone.utc)
    await db.flush()


async def retry_failed_ai_alerts(db: AsyncSession) -> None:
    """重试投递失败的 AI 告警事件（最多 MAX_RETRY 次）。"""
    from app.services.notifications import MAX_RETRY
    rules_by_id: dict = {}
    accounts_by_id: dict = {}
    result = await db.execute(
        select(AIAlertEvent).where(
            AIAlertEvent.status == AlertEventStatus.failed,
            AIAlertEvent.retry_count < MAX_RETRY,
        )
    )
    for event in result.scalars().all():
        if event.rule_id and event.rule_id not in rules_by_id:
            rule = (await db.execute(select(AIAlertRule).where(AIAlertRule.id == event.rule_id))).scalar_one_or_none()
            rules_by_id[event.rule_id] = rule
        rule = rules_by_id.get(event.rule_id) if event.rule_id else None
        if rule is None:
            continue
        if event.provider_account_id not in accounts_by_id:
            acc = (await db.execute(select(AIProviderAccount).where(AIProviderAccount.id == event.provider_account_id))).scalar_one_or_none()
            accounts_by_id[event.provider_account_id] = acc
        account = accounts_by_id.get(event.provider_account_id)
        if account is None:
            continue
        webhook_url = None
        if rule.webhook_url_encrypted and rule.webhook_type:
            try:
                webhook_url = decrypt_text(rule.webhook_url_encrypted)
            except Exception:
                pass
        admin_ids = (
            await db.execute(
                select(User.id).where(
                    User.status == UserStatus.active,
                    User.role.in_([UserRole.admin, UserRole.operator]),
                )
            )
        ).scalars().all()
        await _dispatch_ai_alert_event(
            db, event, account.name, rule.webhook_type, webhook_url,
            rule.notify_inapp, rule.notify_webhook, admin_ids, event.severity,
        )
    await db.commit()


async def _send_ai_webhook(webhook_type: str, url: str, message: str) -> None:
    if webhook_type == "feishu":
        payload = {"msg_type": "text", "content": {"text": message}}
    elif webhook_type == "wecom":
        payload = {"msgtype": "text", "text": {"content": message}}
    else:
        raise ValueError("不支持的 webhook 类型")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

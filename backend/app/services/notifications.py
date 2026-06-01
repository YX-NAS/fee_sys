"""通知发送服务：站内通知 + 飞书/企微 Webhook。"""
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AlertEvent, AlertType, ChannelStatus, Notification, User

logger = logging.getLogger(__name__)

MAX_RETRY = 3


def _build_alert_message(event: AlertEvent, account_name: str) -> tuple[str, str]:
    """返回 (title, content)"""
    if event.alert_type == AlertType.balance_low:
        title = f"⚠️ 余额不足提醒 - {account_name}"
        content = (
            f"账号【{account_name}】当前余额 {event.triggered_value} 已低于阈值 {event.threshold_value}，"
            f"请及时充值以避免服务中断。"
        )
    else:
        title = f"🔔 充值周期提醒 - {account_name}"
        content = f"账号【{account_name}】的充值周期已到，请检查是否需要充值续费。"
    return title, content


async def send_inapp_notification(
    db: AsyncSession,
    event: AlertEvent,
    account_name: str,
    recipient_ids: list[uuid.UUID],
) -> ChannelStatus:
    title, content = _build_alert_message(event, account_name)
    try:
        for uid in recipient_ids:
            notif = Notification(
                user_id=uid,
                alert_event_id=event.id,
                title=title,
                content=content,
            )
            db.add(notif)
        await db.flush()
        return ChannelStatus.sent
    except Exception:
        logger.exception("站内通知创建失败, event_id=%s", event.id)
        return ChannelStatus.failed


async def send_webhook_notification(
    webhook_type: str,
    webhook_url: str,
    event: AlertEvent,
    account_name: str,
) -> ChannelStatus:
    title, content = _build_alert_message(event, account_name)

    if webhook_type == "feishu":
        payload = {
            "msg_type": "text",
            "content": {"text": f"{title}\n{content}"},
        }
    elif webhook_type == "wecom":
        payload = {
            "msgtype": "text",
            "text": {"content": f"{title}\n{content}"},
        }
    else:
        logger.warning("未知 webhook 类型: %s", webhook_type)
        return ChannelStatus.failed

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        return ChannelStatus.sent
    except Exception:
        logger.exception("Webhook 发送失败, type=%s event_id=%s", webhook_type, event.id)
        return ChannelStatus.failed


async def dispatch_alert_event(
    db: AsyncSession,
    event: AlertEvent,
    account_name: str,
    webhook_type: str | None,
    webhook_url: str | None,
    notify_inapp: bool,
    notify_webhook: bool,
    admin_ids: list[uuid.UUID],
) -> None:
    """分发一条提醒事件到所有启用的通道。"""
    if notify_inapp:
        inapp_status = await send_inapp_notification(db, event, account_name, admin_ids)
        event.inapp_status = inapp_status
    else:
        event.inapp_status = ChannelStatus.skipped

    if notify_webhook and webhook_url and webhook_type:
        webhook_status = await send_webhook_notification(webhook_type, webhook_url, event, account_name)
        event.webhook_status = webhook_status
    else:
        event.webhook_status = ChannelStatus.skipped

    if (event.inapp_status in (ChannelStatus.sent, ChannelStatus.skipped) and
            event.webhook_status in (ChannelStatus.sent, ChannelStatus.skipped)):
        from app.models import AlertEventStatus
        event.status = AlertEventStatus.sent
    else:
        from app.models import AlertEventStatus
        event.status = AlertEventStatus.failed
        event.retry_count += 1
        event.last_retry_at = datetime.now(timezone.utc)

    await db.flush()


async def retry_failed_events(db: AsyncSession) -> None:
    """重试投递失败的提醒事件（最多 MAX_RETRY 次）。"""
    from app.models import AlertConfig, AlertEventStatus

    result = await db.execute(
        select(AlertEvent)
        .where(AlertEvent.status == AlertEventStatus.failed)
        .where(AlertEvent.retry_count < MAX_RETRY)
    )
    events = result.scalars().all()

    for event in events:
        # 重新加载配置
        cfg_result = await db.execute(
            select(AlertConfig).where(AlertConfig.id == event.config_id)
        )
        cfg = cfg_result.scalar_one_or_none()
        if cfg is None:
            continue

        from app.models import Account
        acc_result = await db.execute(select(Account).where(Account.id == event.account_id))
        acc = acc_result.scalar_one_or_none()
        if acc is None:
            continue

        from app.security import decrypt_text
        webhook_url = None
        if cfg.webhook_url_encrypted:
            try:
                webhook_url = decrypt_text(cfg.webhook_url_encrypted)
            except Exception:
                pass

        admin_ids = await _get_admin_ids(db)
        await dispatch_alert_event(
            db, event, acc.name,
            cfg.webhook_type, webhook_url,
            cfg.notify_inapp, cfg.notify_webhook,
            admin_ids,
        )

    await db.commit()


async def _get_admin_ids(db: AsyncSession) -> list[uuid.UUID]:
    from app.models import UserRole, UserStatus
    result = await db.execute(
        select(User.id).where(
            User.status == UserStatus.active,
            User.role.in_([UserRole.admin, UserRole.operator]),
        )
    )
    return list(result.scalars().all())

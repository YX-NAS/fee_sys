"""提醒规则扫描与触发服务。"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Account, AccountStatus, AlertConfig, AlertEvent, AlertEventStatus,
    AlertType, ChannelStatus, FeeTransaction, TransactionType,
)
from app.security import decrypt_text
from app.services.notifications import _get_admin_ids, dispatch_alert_event

logger = logging.getLogger(__name__)


async def _get_current_balance(db: AsyncSession, account_id: uuid.UUID) -> float:
    """获取最新余额（取最新一条流水的 balance_after）。"""
    result = await db.execute(
        select(FeeTransaction.balance_after)
        .where(FeeTransaction.account_id == account_id, FeeTransaction.deleted_at.is_(None))
        .order_by(FeeTransaction.transaction_time.desc(), FeeTransaction.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return float(row) if row is not None else 0.0


async def _should_trigger(config: AlertConfig) -> bool:
    """判断是否满足冷却窗口（距上次触发是否超过 cooldown_hours）。"""
    if config.last_triggered_at is None:
        return True
    elapsed = (datetime.now(timezone.utc) - config.last_triggered_at).total_seconds() / 3600
    return elapsed >= config.cooldown_hours


async def check_balance_low(db: AsyncSession) -> None:
    """扫描所有启用的 balance_low 配置，触发低余额提醒。"""
    result = await db.execute(
        select(AlertConfig)
        .join(Account, AlertConfig.account_id == Account.id)
        .where(
            AlertConfig.alert_type == AlertType.balance_low,
            AlertConfig.is_enabled.is_(True),
            Account.status == AccountStatus.active,
            Account.deleted_at.is_(None),
        )
    )
    configs = result.scalars().all()

    for cfg in configs:
        if not await _should_trigger(cfg):
            continue

        balance = await _get_current_balance(db, cfg.account_id)
        threshold = float(cfg.threshold_amount or 0)

        if balance >= threshold:
            continue

        # 创建提醒事件
        event = AlertEvent(
            config_id=cfg.id,
            account_id=cfg.account_id,
            alert_type=AlertType.balance_low,
            triggered_value=balance,
            threshold_value=threshold,
            status=AlertEventStatus.pending,
            inapp_status=ChannelStatus.pending if cfg.notify_inapp else ChannelStatus.skipped,
            webhook_status=ChannelStatus.pending if cfg.notify_webhook else ChannelStatus.skipped,
        )
        db.add(event)
        await db.flush()

        acc_result = await db.execute(select(Account).where(Account.id == cfg.account_id))
        acc = acc_result.scalar_one_or_none()
        if acc is None:
            continue

        webhook_url = None
        if cfg.webhook_url_encrypted:
            try:
                webhook_url = decrypt_text(cfg.webhook_url_encrypted)
            except Exception:
                logger.warning("Webhook URL 解密失败, config_id=%s", cfg.id)

        admin_ids = await _get_admin_ids(db)
        await dispatch_alert_event(
            db, event, acc.name,
            cfg.webhook_type, webhook_url,
            cfg.notify_inapp, cfg.notify_webhook,
            admin_ids,
        )

        cfg.last_triggered_at = datetime.now(timezone.utc)
        logger.info("balance_low 提醒已触发, account_id=%s balance=%.4f threshold=%.4f", cfg.account_id, balance, threshold)

    await db.commit()


async def check_recharge_due(db: AsyncSession) -> None:
    """扫描所有启用的 recharge_due 配置，触发充值周期提醒。"""
    result = await db.execute(
        select(AlertConfig)
        .join(Account, AlertConfig.account_id == Account.id)
        .where(
            AlertConfig.alert_type == AlertType.recharge_due,
            AlertConfig.is_enabled.is_(True),
            Account.status == AccountStatus.active,
            Account.deleted_at.is_(None),
        )
    )
    configs = result.scalars().all()

    now = datetime.now(timezone.utc)
    for cfg in configs:
        if cfg.last_recharge_date is None or cfg.recharge_cycle_days is None:
            continue
        if not await _should_trigger(cfg):
            continue

        days_since = (now - cfg.last_recharge_date).days
        if days_since < cfg.recharge_cycle_days:
            continue

        event = AlertEvent(
            config_id=cfg.id,
            account_id=cfg.account_id,
            alert_type=AlertType.recharge_due,
            triggered_value=None,
            threshold_value=None,
            status=AlertEventStatus.pending,
            inapp_status=ChannelStatus.pending if cfg.notify_inapp else ChannelStatus.skipped,
            webhook_status=ChannelStatus.pending if cfg.notify_webhook else ChannelStatus.skipped,
        )
        db.add(event)
        await db.flush()

        acc_result = await db.execute(select(Account).where(Account.id == cfg.account_id))
        acc = acc_result.scalar_one_or_none()
        if acc is None:
            continue

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

        cfg.last_triggered_at = now
        logger.info("recharge_due 提醒已触发, account_id=%s", cfg.account_id)

    await db.commit()

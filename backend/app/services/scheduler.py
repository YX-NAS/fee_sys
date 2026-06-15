"""APScheduler 定时任务调度配置。"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def _run_balance_check() -> None:
    from app.database import AsyncSessionLocal
    from app.services.alerts import check_balance_low
    logger.info("[Scheduler] 开始扫描余额不足提醒...")
    async with AsyncSessionLocal() as db:
        await check_balance_low(db)
    logger.info("[Scheduler] 余额不足扫描完成")


async def _run_recharge_check() -> None:
    from app.database import AsyncSessionLocal
    from app.services.alerts import check_recharge_due
    logger.info("[Scheduler] 开始扫描充值周期提醒...")
    async with AsyncSessionLocal() as db:
        await check_recharge_due(db)
    logger.info("[Scheduler] 充值周期扫描完成")


async def _run_retry_failed() -> None:
    from app.database import AsyncSessionLocal
    from app.services.notifications import retry_failed_events
    logger.info("[Scheduler] 重试失败提醒事件...")
    async with AsyncSessionLocal() as db:
        await retry_failed_events(db)
    logger.info("[Scheduler] 重试完成")


async def _run_ai_balance_sync() -> None:
    from sqlalchemy import select
    from app.ai_models import AIAccountStatus, AIProviderAccount
    from app.database import AsyncSessionLocal
    from app.services.ai.monitoring import sync_account_balance
    logger.info("[Scheduler] 开始同步 AI 厂商余额...")
    async with AsyncSessionLocal() as db:
        accounts = (await db.execute(
            select(AIProviderAccount).where(AIProviderAccount.status != AIAccountStatus.inactive)
        )).scalars().all()
        for account in accounts:
            try:
                await sync_account_balance(db, account)
                await db.commit()
            except Exception:
                await db.commit()
                logger.exception("AI 余额同步失败, account_id=%s", account.id)
    logger.info("[Scheduler] AI 厂商余额同步完成")


async def _run_deepseek_aggregation() -> None:
    from datetime import datetime, timedelta
    from app.database import AsyncSessionLocal
    from app.services.ai.monitoring import rebuild_deepseek_daily
    target = datetime.now().date() - timedelta(days=1)
    async with AsyncSessionLocal() as db:
        count = await rebuild_deepseek_daily(db, target)
        await db.commit()
    logger.info("[Scheduler] DeepSeek 日汇总完成, date=%s rows=%s", target, count)


async def _run_volcengine_sync() -> None:
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from app.ai_models import AIAccountStatus, AIProvider, AIProviderAccount
    from app.database import AsyncSessionLocal
    from app.services.ai.monitoring import sync_account_usage
    end_date = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=2)
    async with AsyncSessionLocal() as db:
        accounts = (await db.execute(select(AIProviderAccount).where(
            AIProviderAccount.provider == AIProvider.volcengine,
            AIProviderAccount.status != AIAccountStatus.inactive,
        ))).scalars().all()
        for account in accounts:
            await sync_account_usage(db, account, start_date, end_date)
            await db.commit()
    logger.info("[Scheduler] 火山引擎最近三天同步完成")


def start_scheduler() -> None:
    # 每小时整点执行余额检查
    scheduler.add_job(_run_balance_check, CronTrigger(minute=0), id="balance_check", replace_existing=True)
    # 每天 09:00 执行充值周期检查
    scheduler.add_job(_run_recharge_check, CronTrigger(hour=9, minute=0), id="recharge_check", replace_existing=True)
    # 每30分钟重试失败通知
    scheduler.add_job(_run_retry_failed, CronTrigger(minute="*/30"), id="retry_failed", replace_existing=True)
    scheduler.add_job(_run_ai_balance_sync, CronTrigger(minute=5), id="ai_balance_sync", replace_existing=True)
    scheduler.add_job(_run_deepseek_aggregation, CronTrigger(hour=0, minute=10), id="ai_deepseek_daily", replace_existing=True)
    scheduler.add_job(_run_volcengine_sync, CronTrigger(hour=2, minute=0), id="ai_volcengine_daily", replace_existing=True)

    scheduler.start()
    logger.info("APScheduler 已启动")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler 已停止")

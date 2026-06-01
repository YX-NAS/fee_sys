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


def start_scheduler() -> None:
    # 每小时整点执行余额检查
    scheduler.add_job(_run_balance_check, CronTrigger(minute=0), id="balance_check", replace_existing=True)
    # 每天 09:00 执行充值周期检查
    scheduler.add_job(_run_recharge_check, CronTrigger(hour=9, minute=0), id="recharge_check", replace_existing=True)
    # 每30分钟重试失败通知
    scheduler.add_job(_run_retry_failed, CronTrigger(minute="*/30"), id="retry_failed", replace_existing=True)

    scheduler.start()
    logger.info("APScheduler 已启动")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler 已停止")

"""费用分析指标计算服务。"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeeTransaction, TransactionType, Budget


async def get_current_balance(db: AsyncSession, account_id: uuid.UUID) -> Decimal:
    result = await db.execute(
        select(FeeTransaction.balance_after)
        .where(FeeTransaction.account_id == account_id, FeeTransaction.deleted_at.is_(None))
        .order_by(FeeTransaction.transaction_time.desc(), FeeTransaction.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return Decimal(str(row)) if row is not None else Decimal("0")


async def get_period_consume(
    db: AsyncSession,
    account_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(FeeTransaction.amount), 0))
        .where(
            FeeTransaction.account_id == account_id,
            FeeTransaction.transaction_type == TransactionType.consume,
            FeeTransaction.transaction_time >= start,
            FeeTransaction.transaction_time < end,
            FeeTransaction.deleted_at.is_(None),
        )
    )
    return Decimal(str(result.scalar()))


async def get_period_recharge(
    db: AsyncSession,
    account_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(FeeTransaction.amount), 0))
        .where(
            FeeTransaction.account_id == account_id,
            FeeTransaction.transaction_type == TransactionType.recharge,
            FeeTransaction.transaction_time >= start,
            FeeTransaction.transaction_time < end,
            FeeTransaction.deleted_at.is_(None),
        )
    )
    return Decimal(str(result.scalar()))


def _month_range(year: int, month: int) -> tuple[datetime, datetime]:
    import calendar
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return start, end


async def compute_mom_comparison(
    db: AsyncSession,
    account_id: uuid.UUID,
    year: int,
    month: int,
) -> dict:
    """当月消费 vs 上月消费（环比）。"""
    cur_start, cur_end = _month_range(year, month)
    # 上月
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_start, prev_end = _month_range(prev_year, prev_month)

    current = await get_period_consume(db, account_id, cur_start, cur_end)
    previous = await get_period_consume(db, account_id, prev_start, prev_end)

    change = current - previous
    rate = float(change / previous) if previous != 0 else None

    return {
        "current_period": f"{year}-{month:02d}",
        "current_amount": current,
        "compare_period": f"{prev_year}-{prev_month:02d}",
        "compare_amount": previous,
        "change_amount": change,
        "change_rate": rate,
    }


async def compute_yoy_comparison(
    db: AsyncSession,
    account_id: uuid.UUID,
    year: int,
    month: int,
) -> dict:
    """当月消费 vs 去年同月消费（同比）。"""
    cur_start, cur_end = _month_range(year, month)
    prev_start, prev_end = _month_range(year - 1, month)

    current = await get_period_consume(db, account_id, cur_start, cur_end)
    previous = await get_period_consume(db, account_id, prev_start, prev_end)

    change = current - previous
    rate = float(change / previous) if previous != 0 else None

    return {
        "current_period": f"{year}-{month:02d}",
        "current_amount": current,
        "compare_period": f"{year - 1}-{month:02d}",
        "compare_amount": previous,
        "change_amount": change,
        "change_rate": rate,
    }


async def compute_budget_variance(
    db: AsyncSession,
    account_id: uuid.UUID,
    year: int,
    month: int,
) -> dict | None:
    bgt_result = await db.execute(
        select(Budget).where(
            Budget.account_id == account_id,
            Budget.year == year,
            Budget.month == month,
        )
    )
    bgt = bgt_result.scalar_one_or_none()
    if bgt is None:
        return None

    start, end = _month_range(year, month)
    actual = await get_period_consume(db, account_id, start, end)
    variance = actual - bgt.budget_amount
    rate = float(variance / bgt.budget_amount) if bgt.budget_amount != 0 else None

    return {
        "account_id": account_id,
        "year": year,
        "month": month,
        "budget_amount": bgt.budget_amount,
        "actual_amount": actual,
        "variance": variance,
        "variance_rate": rate,
    }


async def get_trend(
    db: AsyncSession,
    account_id: uuid.UUID,
    start: datetime,
    end: datetime,
    granularity: str = "month",  # day / week / month
) -> list[dict]:
    """按时间粒度返回消费/充值趋势。"""
    if granularity == "day":
        trunc = func.date_trunc("day", FeeTransaction.transaction_time)
        fmt = "YYYY-MM-DD"
    elif granularity == "week":
        trunc = func.date_trunc("week", FeeTransaction.transaction_time)
        fmt = "YYYY-WW"
    else:
        trunc = func.date_trunc("month", FeeTransaction.transaction_time)
        fmt = "YYYY-MM"

    result = await db.execute(
        select(
            func.to_char(trunc, fmt).label("period"),
            func.sum(
                func.case((FeeTransaction.transaction_type == TransactionType.consume, FeeTransaction.amount), else_=0)
            ).label("total_consume"),
            func.sum(
                func.case((FeeTransaction.transaction_type == TransactionType.recharge, FeeTransaction.amount), else_=0)
            ).label("total_recharge"),
        )
        .where(
            FeeTransaction.account_id == account_id,
            FeeTransaction.transaction_time >= start,
            FeeTransaction.transaction_time <= end,
            FeeTransaction.deleted_at.is_(None),
        )
        .group_by("period")
        .order_by("period")
    )
    rows = result.all()
    return [
        {
            "period": r.period,
            "total_consume": Decimal(str(r.total_consume or 0)),
            "total_recharge": Decimal(str(r.total_recharge or 0)),
            "net": Decimal(str(r.total_recharge or 0)) - Decimal(str(r.total_consume or 0)),
        }
        for r in rows
    ]


async def get_category_stats(
    db: AsyncSession,
    account_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> list[dict]:
    result = await db.execute(
        select(
            func.coalesce(FeeTransaction.category, "未分类").label("category"),
            func.sum(FeeTransaction.amount).label("total"),
            func.count().label("count"),
        )
        .where(
            FeeTransaction.account_id == account_id,
            FeeTransaction.transaction_type == TransactionType.consume,
            FeeTransaction.transaction_time >= start,
            FeeTransaction.transaction_time <= end,
            FeeTransaction.deleted_at.is_(None),
        )
        .group_by("category")
        .order_by(func.sum(FeeTransaction.amount).desc())
    )
    rows = result.all()
    grand_total = sum(Decimal(str(r.total or 0)) for r in rows)
    return [
        {
            "category": r.category,
            "total": Decimal(str(r.total or 0)),
            "count": r.count,
            "percentage": float(Decimal(str(r.total or 0)) / grand_total * 100) if grand_total else 0.0,
        }
        for r in rows
    ]

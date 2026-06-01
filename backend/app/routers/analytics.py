import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import CurrentUser, DB
from app.models import Account
from app.schemas import (
    AnalyticsSummary, BudgetVarianceResult, CategoryStat,
    ComparisonResult, TrendPoint,
)
from app.services.analytics import (
    compute_budget_variance, compute_mom_comparison, compute_yoy_comparison,
    get_category_stats, get_current_balance, get_period_consume,
    get_period_recharge, get_trend,
)

router = APIRouter(prefix="/api/analytics", tags=["费用分析"])


@router.get("/summary/{account_id}", response_model=AnalyticsSummary)
async def get_summary(account_id: uuid.UUID, db: DB, current_user: CurrentUser):
    await _check_account(db, account_id)
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    import calendar
    prev_month = now.month - 1 if now.month > 1 else 12
    prev_year = now.year if now.month > 1 else now.year - 1
    last_day = calendar.monthrange(prev_year, prev_month)[1]
    prev_start = now.replace(year=prev_year, month=prev_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_end = now.replace(year=prev_year, month=prev_month, day=last_day, hour=23, minute=59, second=59)

    current_balance = await get_current_balance(db, account_id)
    this_month_consume = await get_period_consume(db, account_id, this_month_start, now)
    this_month_recharge = await get_period_recharge(db, account_id, this_month_start, now)
    last_month_consume = await get_period_consume(db, account_id, prev_start, prev_end)
    mom_rate = (
        float((this_month_consume - last_month_consume) / last_month_consume)
        if last_month_consume != 0 else None
    )

    return AnalyticsSummary(
        account_id=account_id,
        current_balance=current_balance,
        this_month_consume=this_month_consume,
        this_month_recharge=this_month_recharge,
        last_month_consume=last_month_consume,
        mom_change_rate=mom_rate,
    )


@router.get("/trend/{account_id}", response_model=list[TrendPoint])
async def get_trend_data(
    account_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    granularity: str = Query("month", regex="^(day|week|month)$"),
):
    await _check_account(db, account_id)
    rows = await get_trend(db, account_id, start_date, end_date, granularity)
    return [TrendPoint(**r) for r in rows]


@router.get("/categories/{account_id}", response_model=list[CategoryStat])
async def get_category_data(
    account_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
):
    await _check_account(db, account_id)
    rows = await get_category_stats(db, account_id, start_date, end_date)
    return [CategoryStat(**r) for r in rows]


@router.get("/comparison/{account_id}", response_model=ComparisonResult)
async def get_comparison(
    account_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    compare_type: str = Query("mom", regex="^(mom|yoy)$"),
):
    await _check_account(db, account_id)
    if compare_type == "mom":
        data = await compute_mom_comparison(db, account_id, year, month)
    else:
        data = await compute_yoy_comparison(db, account_id, year, month)
    return ComparisonResult(**data)


@router.get("/budget-variance/{account_id}", response_model=BudgetVarianceResult | None)
async def get_budget_variance(
    account_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
):
    await _check_account(db, account_id)
    data = await compute_budget_variance(db, account_id, year, month)
    if data is None:
        return None
    return BudgetVarianceResult(**data)


async def _check_account(db, account_id: uuid.UUID):
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="账号不存在")

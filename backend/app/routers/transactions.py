import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DB
from app.models import Account, FeeTransaction, TransactionType
from app.schemas import TransactionCreate, TransactionOut
from app.services.analytics import get_current_balance

router = APIRouter(prefix="/api/transactions", tags=["费用流水"])


@router.get("", response_model=dict)
async def list_transactions(
    db: DB,
    current_user: CurrentUser,
    account_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    category: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(FeeTransaction).where(FeeTransaction.deleted_at.is_(None))
    if account_id:
        query = query.where(FeeTransaction.account_id == account_id)
    if transaction_type:
        query = query.where(FeeTransaction.transaction_type == transaction_type)
    if category:
        query = query.where(FeeTransaction.category == category)
    if start_time:
        query = query.where(FeeTransaction.transaction_time >= start_time)
    if end_time:
        query = query.where(FeeTransaction.transaction_time <= end_time)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(FeeTransaction.transaction_time.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {"total": total, "page": page, "page_size": page_size,
            "items": [TransactionOut.model_validate(t) for t in items]}


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(body: TransactionCreate, db: DB, current_user: CurrentUser):
    # 校验账号存在
    acc_result = await db.execute(
        select(Account).where(Account.id == body.account_id, Account.deleted_at.is_(None))
    )
    if acc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 幂等检查
    if body.idempotency_key:
        existing = await db.execute(
            select(FeeTransaction).where(FeeTransaction.idempotency_key == body.idempotency_key)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="重复提交：idempotency_key 已存在")

    # 计算新余额
    current_balance = await get_current_balance(db, body.account_id)
    if body.transaction_type in (TransactionType.consume, TransactionType.adjustment):
        new_balance = current_balance - body.amount
    elif body.transaction_type == TransactionType.refund:
        new_balance = current_balance + body.amount
    else:  # recharge
        new_balance = current_balance + body.amount

    txn = FeeTransaction(
        account_id=body.account_id,
        transaction_type=body.transaction_type,
        amount=body.amount,
        balance_after=new_balance,
        description=body.description,
        category=body.category,
        idempotency_key=body.idempotency_key,
        transaction_time=body.transaction_time or datetime.now(timezone.utc),
        created_by_id=current_user.id,
    )
    db.add(txn)
    await db.flush()

    # 如果是充值，更新 alert_configs.last_recharge_date
    if body.transaction_type == TransactionType.recharge:
        from app.models import AlertConfig, AlertType
        cfg_result = await db.execute(
            select(AlertConfig).where(
                AlertConfig.account_id == body.account_id,
                AlertConfig.alert_type == AlertType.recharge_due,
            )
        )
        cfg = cfg_result.scalar_one_or_none()
        if cfg:
            cfg.last_recharge_date = txn.transaction_time

    # 触发余额低提醒检查（异步，不阻塞响应）
    from app.services.alerts import check_balance_low
    from app.database import AsyncSessionLocal
    import asyncio
    asyncio.create_task(_async_check_balance(body.account_id))

    return TransactionOut.model_validate(txn)


async def _async_check_balance(account_id: uuid.UUID):
    """在后台异步触发单个账号的余额检查，不影响主流程。"""
    try:
        from app.database import AsyncSessionLocal
        from app.models import AlertConfig, AlertType
        from sqlalchemy import select as sa_select
        async with AsyncSessionLocal() as db:
            cfg_result = await db.execute(
                sa_select(AlertConfig).where(
                    AlertConfig.account_id == account_id,
                    AlertConfig.alert_type == AlertType.balance_low,
                    AlertConfig.is_enabled.is_(True),
                )
            )
            if cfg_result.scalar_one_or_none():
                from app.services.alerts import check_balance_low
                await check_balance_low(db)
    except Exception:
        pass


@router.get("/{txn_id}", response_model=TransactionOut)
async def get_transaction(txn_id: uuid.UUID, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(FeeTransaction).where(FeeTransaction.id == txn_id, FeeTransaction.deleted_at.is_(None))
    )
    txn = result.scalar_one_or_none()
    if txn is None:
        raise HTTPException(status_code=404, detail="流水记录不存在")
    return TransactionOut.model_validate(txn)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_transaction(txn_id: uuid.UUID, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(FeeTransaction).where(FeeTransaction.id == txn_id, FeeTransaction.deleted_at.is_(None))
    )
    txn = result.scalar_one_or_none()
    if txn is None:
        raise HTTPException(status_code=404, detail="流水记录不存在")
    txn.deleted_at = datetime.now(timezone.utc)

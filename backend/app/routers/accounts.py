import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DB, require_roles
from app.models import Account, AccountStatus, FeeTransaction
from app.schemas import AccountCreate, AccountOut, AccountUpdate
from app.services.analytics import get_current_balance

router = APIRouter(prefix="/api/accounts", tags=["账号管理"])


@router.get("", response_model=dict)
async def list_accounts(
    db: DB,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: AccountStatus | None = None,
    keyword: str | None = None,
):
    query = select(Account).where(Account.deleted_at.is_(None))
    if status:
        query = query.where(Account.status == status)
    if keyword:
        query = query.where(Account.name.ilike(f"%{keyword}%"))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(Account.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    accounts = result.scalars().all()

    items = []
    for acc in accounts:
        out = AccountOut.model_validate(acc)
        out.current_balance = await get_current_balance(db, acc.id)
        items.append(out)

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountCreate, db: DB, current_user: CurrentUser):
    acc = Account(**body.model_dump(), created_by_id=current_user.id)
    db.add(acc)
    await db.flush()
    out = AccountOut.model_validate(acc)
    out.current_balance = Decimal("0")
    return out


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: uuid.UUID, db: DB, current_user: CurrentUser):
    acc = await _get_or_404(db, account_id)
    out = AccountOut.model_validate(acc)
    out.current_balance = await get_current_balance(db, acc.id)
    return out


@router.put("/{account_id}", response_model=AccountOut)
async def update_account(account_id: uuid.UUID, body: AccountUpdate, db: DB, current_user: CurrentUser):
    acc = await _get_or_404(db, account_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(acc, field, value)
    await db.flush()
    out = AccountOut.model_validate(acc)
    out.current_balance = await get_current_balance(db, acc.id)
    return out


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
    _=require_roles("admin"),
):
    acc = await _get_or_404(db, account_id)
    acc.deleted_at = datetime.now(timezone.utc)
    acc.status = AccountStatus.archived


async def _get_or_404(db, account_id: uuid.UUID) -> Account:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    acc = result.scalar_one_or_none()
    if acc is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return acc


from decimal import Decimal

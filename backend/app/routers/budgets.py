import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from app.dependencies import CurrentUser, DB, require_roles
from app.models import Budget
from app.schemas import BudgetCreate, BudgetOut, BudgetUpdate

router = APIRouter(prefix="/api/budgets", tags=["预算管理"])


@router.get("", response_model=dict)
async def list_budgets(
    db: DB,
    current_user: CurrentUser,
    account_id: uuid.UUID | None = None,
    year: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Budget)
    if account_id:
        query = query.where(Budget.account_id == account_id)
    if year:
        query = query.where(Budget.year == year)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(Budget.year.desc(), Budget.month.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [BudgetOut.model_validate(b) for b in items]}


@router.post("", response_model=BudgetOut)
async def create_budget(body: BudgetCreate, db: DB, current_user: CurrentUser):
    existing = await db.execute(
        select(Budget).where(
            Budget.account_id == body.account_id,
            Budget.year == body.year,
            Budget.month == body.month,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该账号该月预算已存在")

    bgt = Budget(**body.model_dump(), created_by_id=current_user.id)
    db.add(bgt)
    await db.flush()
    return BudgetOut.model_validate(bgt)


@router.put("/{budget_id}", response_model=BudgetOut)
async def update_budget(budget_id: uuid.UUID, body: BudgetUpdate, db: DB, current_user: CurrentUser):
    bgt = await _get_or_404(db, budget_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(bgt, k, v)
    await db.flush()
    return BudgetOut.model_validate(bgt)


@router.delete("/{budget_id}")
async def delete_budget(budget_id: uuid.UUID, db: DB, current_user: CurrentUser):
    bgt = await _get_or_404(db, budget_id)
    await db.delete(bgt)
    return {"message": "预算已删除"}


async def _get_or_404(db, budget_id: uuid.UUID) -> Budget:
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    bgt = result.scalar_one_or_none()
    if bgt is None:
        raise HTTPException(status_code=404, detail="预算不存在")
    return bgt

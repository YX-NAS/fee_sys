import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import (
    AccountStatus, AccountType, AlertEventStatus, AlertType,
    ChannelStatus, TransactionType, UserRole, UserStatus,
)


# ── Common ────────────────────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PagedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


# ── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.viewer


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: UserRole | None = None
    status: UserStatus | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Account ───────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    account_type: AccountType = AccountType.other
    description: str | None = None
    tags: str | None = None


class AccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    account_type: AccountType | None = None
    description: str | None = None
    tags: str | None = None
    status: AccountStatus | None = None


class AccountOut(BaseModel):
    id: uuid.UUID
    name: str
    account_type: AccountType
    status: AccountStatus
    description: str | None
    tags: str | None
    current_balance: Decimal | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── FeeTransaction ────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    transaction_type: TransactionType
    amount: Decimal = Field(..., gt=0)
    description: str | None = None
    category: str | None = None
    idempotency_key: str | None = None
    transaction_time: datetime | None = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount 必须为正数")
        return v


class TransactionOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    transaction_type: TransactionType
    amount: Decimal
    balance_after: Decimal
    description: str | None
    category: str | None
    idempotency_key: str | None
    transaction_time: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── AlertConfig ───────────────────────────────────────────────────────────────

class AlertConfigCreate(BaseModel):
    account_id: uuid.UUID
    alert_type: AlertType
    threshold_amount: Decimal | None = None
    recharge_cycle_days: int | None = Field(None, ge=1)
    last_recharge_date: datetime | None = None
    cooldown_hours: int = Field(24, ge=1, le=720)
    notify_inapp: bool = True
    notify_webhook: bool = False
    webhook_type: str | None = None
    webhook_url: str | None = None  # plaintext input, stored encrypted

    @model_validator(mode="after")
    def validate_alert_fields(self):
        if self.alert_type == AlertType.balance_low and self.threshold_amount is None:
            raise ValueError("balance_low 类型必须提供 threshold_amount")
        if self.alert_type == AlertType.recharge_due and self.recharge_cycle_days is None:
            raise ValueError("recharge_due 类型必须提供 recharge_cycle_days")
        if self.notify_webhook and not self.webhook_url:
            raise ValueError("启用 webhook 时必须提供 webhook_url")
        return self


class AlertConfigUpdate(BaseModel):
    threshold_amount: Decimal | None = None
    recharge_cycle_days: int | None = Field(None, ge=1)
    last_recharge_date: datetime | None = None
    cooldown_hours: int | None = Field(None, ge=1, le=720)
    notify_inapp: bool | None = None
    notify_webhook: bool | None = None
    webhook_type: str | None = None
    webhook_url: str | None = None
    is_enabled: bool | None = None


class AlertConfigOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    alert_type: AlertType
    threshold_amount: Decimal | None
    recharge_cycle_days: int | None
    last_recharge_date: datetime | None
    cooldown_hours: int
    notify_inapp: bool
    notify_webhook: bool
    webhook_type: str | None
    is_enabled: bool
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── AlertEvent ────────────────────────────────────────────────────────────────

class AlertEventOut(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID | None
    account_id: uuid.UUID
    alert_type: AlertType
    triggered_value: Decimal | None
    threshold_value: Decimal | None
    status: AlertEventStatus
    inapp_status: ChannelStatus
    webhook_status: ChannelStatus
    retry_count: int
    created_at: datetime
    acknowledged_at: datetime | None

    model_config = {"from_attributes": True}


# ── Notification ──────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: uuid.UUID
    alert_event_id: uuid.UUID | None
    title: str
    content: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Budget ────────────────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    account_id: uuid.UUID
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    budget_amount: Decimal = Field(..., gt=0)
    note: str | None = None


class BudgetUpdate(BaseModel):
    budget_amount: Decimal | None = Field(None, gt=0)
    note: str | None = None


class BudgetOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    year: int
    month: int
    budget_amount: Decimal
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Analytics ─────────────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    period: str  # e.g. "2026-01"
    total_consume: Decimal
    total_recharge: Decimal
    net: Decimal


class CategoryStat(BaseModel):
    category: str
    total: Decimal
    count: int
    percentage: float


class ComparisonResult(BaseModel):
    current_period: str
    current_amount: Decimal
    compare_period: str
    compare_amount: Decimal
    change_amount: Decimal
    change_rate: float | None  # None if compare is 0


class BudgetVarianceResult(BaseModel):
    account_id: uuid.UUID
    year: int
    month: int
    budget_amount: Decimal
    actual_amount: Decimal
    variance: Decimal
    variance_rate: float | None


class AnalyticsSummary(BaseModel):
    account_id: uuid.UUID
    current_balance: Decimal
    this_month_consume: Decimal
    this_month_recharge: Decimal
    last_month_consume: Decimal
    mom_change_rate: float | None

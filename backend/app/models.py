import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class AccountType(str, enum.Enum):
    cloud = "cloud"
    subscription = "subscription"
    prepaid = "prepaid"
    other = "other"


class AccountStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class TransactionType(str, enum.Enum):
    recharge = "recharge"
    consume = "consume"
    adjustment = "adjustment"
    refund = "refund"


class AlertType(str, enum.Enum):
    balance_low = "balance_low"
    recharge_due = "recharge_due"


class AlertEventStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    acknowledged = "acknowledged"


class ChannelStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


# ── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.viewer, nullable=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.active, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="creator", foreign_keys="Account.created_by_id")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")


# ── Account ───────────────────────────────────────────────────────────────────

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType), default=AccountType.other, nullable=False)
    status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), default=AccountStatus.active, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(512), nullable=True)  # comma-separated
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped["User | None"] = relationship("User", back_populates="accounts", foreign_keys=[created_by_id])
    transactions: Mapped[list["FeeTransaction"]] = relationship("FeeTransaction", back_populates="account")
    alert_configs: Mapped[list["AlertConfig"]] = relationship("AlertConfig", back_populates="account")
    budgets: Mapped[list["Budget"]] = relationship("Budget", back_populates="account")

    __table_args__ = (
        Index("ix_accounts_status_deleted", "status", "deleted_at"),
    )


# ── FeeTransaction ────────────────────────────────────────────────────────────

class FeeTransaction(Base):
    __tablename__ = "fee_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True)
    transaction_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["Account"] = relationship("Account", back_populates="transactions")

    __table_args__ = (
        Index("ix_fee_txn_account_time", "account_id", "transaction_time"),
        Index("ix_fee_txn_category_time", "category", "transaction_time"),
    )


# ── AlertConfig ───────────────────────────────────────────────────────────────

class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    # balance_low
    threshold_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    # recharge_due
    recharge_cycle_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_recharge_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # common
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    notify_inapp: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_webhook: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # feishu / wecom
    webhook_url_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="alert_configs")
    events: Mapped[list["AlertEvent"]] = relationship("AlertEvent", back_populates="config")

    __table_args__ = (
        UniqueConstraint("account_id", "alert_type", name="uq_alert_config_account_type"),
    )


# ── AlertEvent ────────────────────────────────────────────────────────────────

class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alert_configs.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    triggered_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    status: Mapped[AlertEventStatus] = mapped_column(Enum(AlertEventStatus), default=AlertEventStatus.pending, nullable=False, index=True)
    inapp_status: Mapped[ChannelStatus] = mapped_column(Enum(ChannelStatus), default=ChannelStatus.pending, nullable=False)
    webhook_status: Mapped[ChannelStatus] = mapped_column(Enum(ChannelStatus), default=ChannelStatus.skipped, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    config: Mapped["AlertConfig | None"] = relationship("AlertConfig", back_populates="events")

    __table_args__ = (
        Index("ix_alert_events_status_created", "status", "created_at"),
    )


# ── Notification (站内通知) ────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("alert_events.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )


# ── Budget ────────────────────────────────────────────────────────────────────

class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="budgets")

    __table_args__ = (
        UniqueConstraint("account_id", "year", "month", name="uq_budget_account_year_month"),
    )

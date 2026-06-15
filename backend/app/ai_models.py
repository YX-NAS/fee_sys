import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models import utcnow


class AIProvider(str, enum.Enum):
    deepseek = "deepseek"
    volcengine = "volcengine"
    kimi = "kimi"
    alibaba = "alibaba"
    huawei = "huawei"
    zhipu = "zhipu"
    siliconflow = "siliconflow"


class AIAccountStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class AISyncStatus(str, enum.Enum):
    never = "never"
    running = "running"
    success = "success"
    failed = "failed"


class AICostSource(str, enum.Enum):
    provider = "provider"
    calculated = "calculated"


class AIGatewayKeyStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class AIRequestStatus(str, enum.Enum):
    success = "success"
    failed = "failed"
    incomplete = "incomplete"


class AIAlertType(str, enum.Enum):
    balance_low = "balance_low"
    sync_failed = "sync_failed"


class AIAlertEventStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"


class AIProviderAccount(Base):
    __tablename__ = "ai_provider_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[AIProvider] = mapped_column(Enum(AIProvider), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    portal_username_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    portal_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_account_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[AIAccountStatus] = mapped_column(Enum(AIAccountStatus), default=AIAccountStatus.active, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[AISyncStatus] = mapped_column(Enum(AISyncStatus), default=AISyncStatus.never, nullable=False)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    gateway_keys: Mapped[list["AIGatewayKey"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    api_credentials: Mapped[list["AIProviderAPICredential"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    daily_usage: Mapped[list["AIDailyUsage"]] = relationship(back_populates="account", cascade="all, delete-orphan")

    @property
    def portal_credentials_configured(self) -> bool:
        return bool(self.portal_username_encrypted and self.portal_password_encrypted)


class AIProviderAPICredential(Base):
    __tablename__ = "ai_provider_api_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    key_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    account: Mapped["AIProviderAccount"] = relationship(back_populates="api_credentials")

    __table_args__ = (
        Index("ix_ai_provider_api_credential_account_default", "provider_account_id", "is_default"),
    )


class AIGatewayKey(Base):
    __tablename__ = "ai_gateway_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[AIGatewayKeyStatus] = mapped_column(Enum(AIGatewayKeyStatus), default=AIGatewayKeyStatus.active, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    account: Mapped["AIProviderAccount"] = relationship(back_populates="gateway_keys")


class AIGatewayRequest(Base):
    __tablename__ = "ai_gateway_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    gateway_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_gateway_keys.id", ondelete="SET NULL"), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cached_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    calculated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    status: Mapped[AIRequestStatus] = mapped_column(Enum(AIRequestStatus), nullable=False, index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (Index("ix_ai_gateway_request_account_date", "provider_account_id", "usage_date"),)


class AIDailyUsage(Base):
    __tablename__ = "ai_daily_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cached_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    request_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    provider_reported_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    calculated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    cost_source: Mapped[AICostSource] = mapped_column(Enum(AICostSource), default=AICostSource.calculated, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    account: Mapped["AIProviderAccount"] = relationship(back_populates="daily_usage")

    __table_args__ = (
        UniqueConstraint("provider_account_id", "usage_date", "model", name="uq_ai_daily_account_date_model"),
        Index("ix_ai_daily_usage_date_provider", "usage_date", "provider_account_id"),
    )


class AIBalanceSnapshot(Base):
    __tablename__ = "ai_balance_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    available_balance: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    credit_granted: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    credit_used: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)


class AIModelPrice(Base):
    __tablename__ = "ai_model_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[AIProvider] = mapped_column(Enum(AIProvider), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    input_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"), nullable=False)
    output_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"), nullable=False)
    cached_input_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"), nullable=False)
    reasoning_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"), nullable=False)
    unit_tokens: Mapped[int] = mapped_column(BigInteger, default=1_000_000, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("provider", "model", "effective_from", name="uq_ai_price_provider_model_from"),)


class AISyncRun(Base):
    __tablename__ = "ai_sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    sync_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[AISyncStatus] = mapped_column(Enum(AISyncStatus), nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIAlertRule(Base):
    __tablename__ = "ai_alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type: Mapped[AIAlertType] = mapped_column(Enum(AIAlertType), nullable=False)
    threshold_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    notify_inapp: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_webhook: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    webhook_url_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("provider_account_id", "alert_type", name="uq_ai_alert_account_type"),)


class AIAlertEvent(Base):
    __tablename__ = "ai_alert_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_alert_rules.id", ondelete="SET NULL"), nullable=True)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type: Mapped[AIAlertType] = mapped_column(Enum(AIAlertType), nullable=False)
    triggered_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AIAlertEventStatus] = mapped_column(Enum(AIAlertEventStatus), default=AIAlertEventStatus.open, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

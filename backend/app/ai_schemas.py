import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from app.ai_models import (
    AIAccountStatus, AIAlertEventStatus, AIAlertType, AICostSource,
    AIGatewayKeyStatus, AIProvider, AISyncStatus,
)


class AIAccountCreate(BaseModel):
    provider: AIProvider
    name: str = Field(min_length=1, max_length=128)
    portal_username: str
    portal_password: str
    currency: str = Field("CNY", min_length=3, max_length=8)
    timezone: str = "Asia/Shanghai"
    provider_account_ref: str | None = None
    base_url: str | None = None


class AIAccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    portal_username: str | None = None
    portal_password: str | None = None
    currency: str | None = None
    timezone: str | None = None
    provider_account_ref: str | None = None
    base_url: str | None = None
    status: AIAccountStatus | None = None


def _validate_provider_url(provider: AIProvider, base_url: str | None) -> None:
    if not base_url:
        return
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise ValueError("厂商 API 地址必须使用 HTTPS")
    if provider == AIProvider.deepseek and parsed.hostname != "api.deepseek.com":
        raise ValueError("DeepSeek API 地址仅允许 api.deepseek.com")
    if provider == AIProvider.volcengine and parsed.hostname != "open.volcengineapi.com":
        raise ValueError("火山引擎 API 地址仅允许 open.volcengineapi.com")
        raise ValueError("火山引擎 API 地址仅允许 open.volcengineapi.com")
    if provider == AIProvider.kimi and parsed.hostname not in ("api.moonshot.cn", "api.moonshot.net"):
        raise ValueError("Kimi API 地址仅允许 api.moonshot.cn")
    if provider == AIProvider.alibaba and parsed.hostname != "dashscope.aliyuncs.com":
        raise ValueError("阿里云 DashScope API 地址仅允许 dashscope.aliyuncs.com")
    if provider == AIProvider.huawei and not parsed.hostname.endswith(".myhuaweicloud.com"):
        raise ValueError("华为云 API 地址必须以 .myhuaweicloud.com 结尾")
    if provider == AIProvider.zhipu and parsed.hostname != "open.bigmodel.cn":
        raise ValueError("智谱 API 地址仅允许 open.bigmodel.cn")
    if provider == AIProvider.siliconflow and parsed.hostname != "api.siliconflow.cn":
        raise ValueError("硅基流动 API 地址仅允许 api.siliconflow.cn")
        raise ValueError("华为云 API 地址必须以 .myhuaweicloud.com 结尾")
        raise ValueError("火山引擎 API 地址仅允许 open.volcengineapi.com")


class AIAccountOut(BaseModel):
    id: uuid.UUID
    provider: AIProvider
    name: str
    currency: str
    timezone: str
    provider_account_ref: str | None
    base_url: str | None
    status: AIAccountStatus
    portal_credentials_configured: bool
    api_credentials_configured: bool = False
    api_credentials_count: int = 0
    last_sync_at: datetime | None
    last_sync_status: AISyncStatus
    last_sync_error: str | None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AITestConnectionOut(BaseModel):
    ok: bool
    capabilities: dict[str, bool]
    message: str


class AIProviderAPICredentialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    credential_type: str = Field(min_length=1, max_length=32)
    credentials: dict[str, str]
    is_default: bool = False


class AIProviderAPICredentialUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    credentials: dict[str, str] | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class AIProviderAPICredentialOut(BaseModel):
    id: uuid.UUID
    provider_account_id: uuid.UUID
    name: str
    credential_type: str
    key_hint: str | None
    is_active: bool
    is_default: bool
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_error: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AISyncRequest(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 90:
            raise ValueError("单次回补最多 90 天")
        return self


class AIGatewayKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    rate_limit_per_minute: int = Field(60, ge=1, le=10000)
    expires_at: datetime | None = None


class AIGatewayKeyOut(BaseModel):
    id: uuid.UUID
    provider_account_id: uuid.UUID
    name: str
    key_prefix: str
    status: AIGatewayKeyStatus
    rate_limit_per_minute: int
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class AIGatewayKeyCreated(AIGatewayKeyOut):
    key: str


class AIPriceCreate(BaseModel):
    provider: AIProvider
    model: str = Field(min_length=1, max_length=256)
    input_price: Decimal = Field(ge=0)
    output_price: Decimal = Field(ge=0)
    cached_input_price: Decimal = Field(ge=0, default=Decimal("0"))
    reasoning_price: Decimal = Field(ge=0, default=Decimal("0"))
    unit_tokens: int = Field(1_000_000, ge=1)
    currency: str = "CNY"
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("失效日期不能早于生效日期")
        return self


class AIPriceOut(AIPriceCreate):
    id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class AIAlertRuleUpsert(BaseModel):
    alert_type: AIAlertType
    threshold_amount: Decimal | None = Field(None, ge=0)
    failure_count: int = Field(2, ge=1, le=20)
    cooldown_hours: int = Field(24, ge=1, le=720)
    notify_inapp: bool = True
    notify_webhook: bool = False
    webhook_type: str | None = None
    webhook_url: str | None = None
    is_enabled: bool = False


class AIAlertRuleOut(BaseModel):
    id: uuid.UUID
    provider_account_id: uuid.UUID
    alert_type: AIAlertType
    threshold_amount: Decimal | None
    failure_count: int
    cooldown_hours: int
    notify_inapp: bool
    notify_webhook: bool
    webhook_type: str | None
    is_enabled: bool
    last_triggered_at: datetime | None
    model_config = {"from_attributes": True}


class AIAlertEventOut(BaseModel):
    id: uuid.UUID
    provider_account_id: uuid.UUID
    alert_type: AIAlertType
    triggered_value: Decimal | None
    threshold_value: Decimal | None
    message: str
    status: AIAlertEventStatus
    created_at: datetime
    acknowledged_at: datetime | None
    model_config = {"from_attributes": True}

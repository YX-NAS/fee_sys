from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_models import AIProvider, AIProviderAccount, AIProviderAPICredential
from app.services.ai.security import decrypt_credentials


def credential_type_for(provider: AIProvider) -> str:
    if provider in (AIProvider.deepseek, AIProvider.kimi):
        return "api_key"
    return "ak_sk"


def validate_api_credentials(
    provider: AIProvider, credential_type: str, credentials: dict[str, str],
) -> None:
    expected_type = credential_type_for(provider)
    if credential_type != expected_type:
        raise ValueError(f"{provider.value} 仅支持 {expected_type} 类型凭据")
    required = {"api_key"} if provider in (AIProvider.deepseek, AIProvider.kimi) else {"access_key_id", "secret_access_key"}
    if not required.issubset(credentials) or any(not str(credentials[key]).strip() for key in required):
        raise ValueError("官方 API 凭据缺少必填字段")


def api_credential_hint(provider: AIProvider, credentials: dict[str, str]) -> str:
    value = credentials["api_key"] if provider in (AIProvider.deepseek, AIProvider.kimi) else credentials["access_key_id"]
    value = str(value)
    if len(value) <= 8:
        return f"{value[:2]}***"
    return f"{value[:4]}***{value[-4:]}"


async def get_default_api_credential(
    db: AsyncSession, account: AIProviderAccount,
) -> AIProviderAPICredential:
    item = (await db.execute(
        select(AIProviderAPICredential)
        .where(
            AIProviderAPICredential.provider_account_id == account.id,
            AIProviderAPICredential.is_active.is_(True),
        )
        .order_by(AIProviderAPICredential.is_default.desc(), AIProviderAPICredential.created_at.asc())
        .limit(1)
    )).scalar_one_or_none()
    if not item:
        raise RuntimeError("该厂商账号尚未配置启用的官方 API 凭据")
    return item


async def load_default_api_credentials(
    db: AsyncSession, account: AIProviderAccount,
) -> dict[str, str]:
    item = await get_default_api_credential(db, account)
    return decrypt_credentials(item.credentials_encrypted)

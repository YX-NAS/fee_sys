from decimal import Decimal

import httpx

from app.config import get_settings
from app.services.ai.providers.base import ProviderAdapter


class DeepSeekAdapter(ProviderAdapter):
    capabilities = {"usage": False, "balance": True, "cost": False, "gateway": True}

    def __init__(self, credentials: dict[str, str], base_url: str | None = None):
        self.api_key = credentials["api_key"]
        self.base_url = (base_url or get_settings().DEEPSEEK_BASE_URL).rstrip("/")

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def test_connection(self) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/models", headers=self.headers())
            response.raise_for_status()
        return "DeepSeek 连接正常"

    async def fetch_balance(self) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/user/balance", headers=self.headers())
            response.raise_for_status()
            payload = response.json()
        balances = payload.get("balance_infos") or []
        if not balances:
            raise RuntimeError("DeepSeek 未返回余额信息")
        cny = next((item for item in balances if item.get("currency") == "CNY"), balances[0])
        return {
            "available_balance": Decimal(str(cny.get("total_balance", "0"))),
            "credit_granted": Decimal(str(cny.get("granted_balance", "0"))),
            "credit_used": None,
            "currency": cny.get("currency", "CNY"),
        }

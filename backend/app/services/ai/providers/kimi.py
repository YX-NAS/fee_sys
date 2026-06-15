from decimal import Decimal

import httpx

from app.config import get_settings
from app.services.ai.providers.base import ProviderAdapter


class KimiAdapter(ProviderAdapter):
    capabilities = {"usage": False, "balance": True, "cost": False, "gateway": True}

    def __init__(self, credentials: dict[str, str], base_url: str | None = None):
        self.api_key = credentials["api_key"]
        self.base_url = (base_url or "https://api.moonshot.cn/v1").rstrip("/")

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def test_connection(self) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/models", headers=self.headers())
            response.raise_for_status()
        return "Kimi 连接正常"

    async def fetch_balance(self) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/users/me/balance", headers=self.headers())
            response.raise_for_status()
            payload = response.json()
        data = (payload.get("data") or {})
        return {
            "available_balance": Decimal(str(data.get("total_balance", "0"))),
            "credit_granted": Decimal(str(data.get("granted_balance", "0"))),
            "credit_used": None,
            "currency": "CNY",
        }

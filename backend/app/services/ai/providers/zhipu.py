from decimal import Decimal

import httpx

from app.services.ai.providers.base import ProviderAdapter


class ZhipuAdapter(ProviderAdapter):
    capabilities = {"usage": True, "balance": True, "cost": False, "gateway": False}

    def __init__(self, credentials: dict[str, str], base_url: str | None = None):
        self.api_key = credentials["api_key"]
        self.base_url = (base_url or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def test_connection(self) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/models", headers=self.headers())
            response.raise_for_status()
        return "智谱连接正常"

    async def fetch_balance(self) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/account/info", headers=self.headers())
            response.raise_for_status()
            payload = response.json()
        data = (payload.get("data") or {})
        bal = data.get("balance") or data.get("available_balance") or 0
        return {
            "available_balance": Decimal(str(bal)),
            "credit_granted": None,
            "credit_used": None,
            "currency": "CNY",
        }

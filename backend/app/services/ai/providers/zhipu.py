from decimal import Decimal

import httpx

from app.services.ai.providers.base import ProviderAdapter


class ZhipuAdapter(ProviderAdapter):
    capabilities = {"usage": False, "balance": True, "cost": False, "gateway": False}

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
        # Zhipu balance is available via the web session API, not the paas/v4 API.
        # Try the user account endpoint on the main domain.
        endpoints = [
            "/user/info",
            "/api/user/info",
            "/account/info",
            "/api/account/info",
        ]
        last_error = None
        async with httpx.AsyncClient(timeout=20) as client:
            for ep in endpoints:
                try:
                    response = await client.get(ep, headers=self.headers())
                    response.raise_for_status()
                    payload = response.json()
                    data = (payload.get("data") or payload or {})
                    bal = data.get("balance") or data.get("available_balance") or data.get("amount") or 0
                    return {
                        "available_balance": Decimal(str(bal)),
                        "credit_granted": None,
                        "credit_used": None,
                        "currency": "CNY",
                    }
                except Exception as exc:
                    last_error = exc
                    continue
        raise RuntimeError(f"智谱余额接口不可用: {last_error}")

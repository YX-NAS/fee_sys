from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from app.services.ai.providers.base import ProviderAdapter


class SiliconFlowAdapter(ProviderAdapter):
    capabilities = {"usage": False, "balance": True, "cost": False, "gateway": True}

    def __init__(self, credentials: dict[str, str], base_url: str | None = None):
        self.api_key = credentials["api_key"]
        self.base_url = (base_url or "https://api.siliconflow.cn/v1").rstrip("/")

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def test_connection(self) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/models", headers=self.headers())
            response.raise_for_status()
        return "硅基流动连接正常"

    async def fetch_balance(self) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/user/info", headers=self.headers())
            response.raise_for_status()
            payload = response.json()
        data = (payload.get("data") or {})
        bal = data.get("balance") or data.get("totalBalance") or data.get("available_balance") or 0
        return {
            "available_balance": Decimal(str(bal)),
            "credit_granted": None,
            "credit_used": None,
            "currency": "CNY",
        }

    async def fetch_usage(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/user/usage",
                params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                headers=self.headers(),
            )
            response.raise_for_status()
            payload = response.json()
        data = (payload.get("data") or {})
        items = data.get("records") or data.get("items") or data.get("models") or []
        for item in items:
            if isinstance(item, dict):
                rows.append({
                    "usage_date": start_date,
                    "model": item.get("model") or item.get("model_name", "unknown"),
                    "input_tokens": int(item.get("input_tokens") or item.get("prompt_tokens") or 0),
                    "output_tokens": int(item.get("output_tokens") or item.get("completion_tokens") or 0),
                    "cached_input_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": int(item.get("total_tokens") or 0),
                    "request_count": int(item.get("request_count") or item.get("count") or 0),
                })
        if not rows:
            summary = data.get("summary") or {}
            if summary.get("total_tokens"):
                rows.append({
                    "usage_date": start_date,
                    "model": "siliconflow-batch",
                    "input_tokens": int(summary.get("input_tokens") or summary.get("prompt_tokens") or 0),
                    "output_tokens": int(summary.get("output_tokens") or summary.get("completion_tokens") or 0),
                    "cached_input_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": int(summary.get("total_tokens") or 0),
                    "request_count": int(summary.get("request_count") or 0),
                })
        return rows

import asyncio
import json
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from app.services.ai.providers.base import ProviderAdapter


class HuaweiAdapter(ProviderAdapter):
    capabilities = {"usage": True, "balance": True, "cost": False, "gateway": False}

    def __init__(self, credentials: dict[str, str], base_url: str | None = None):
        self.ak = credentials["access_key_id"]
        self.sk = credentials["secret_access_key"]
        self.project_id = credentials.get("project_id", "")
        self.region = credentials.get("region", "cn-north-4")
        self.iam_host = "iam.myhuaweicloud.com"

    def _token(self) -> str:
        body = json.dumps({
            "auth": {
                "identity": {
                    "methods": ["hw_ak_sk"],
                    "hw_ak_sk": {
                        "access_key": self.ak,
                        "secret_key": self.sk,
                    },
                },
                "scope": {"project": {"name": self.region}},
            }
        })
        headers = {"Content-Type": "application/json;charset=utf8"}
        response = httpx.post(
            f"https://{self.iam_host}/v3/auth/tokens",
            headers=headers, content=body, timeout=30,
        )
        response.raise_for_status()
        return response.headers["x-subject-token"]

    def _headers(self) -> dict[str, str]:
        return {
            "X-Auth-Token": self._token(),
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> str:
        await asyncio.to_thread(self._token)
        return "华为云连接正常"

    async def fetch_balance(self) -> dict[str, Any]:
        def call():
            headers = self._headers()
            body = json.dumps({"customer_id": "", "include_credit": 1})
            response = httpx.post(
                f"https://bss.myhuaweicloud.com/v2/accounts/customer-accounts/balances",
                headers=headers, content=body, timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            debts = (payload.get("account_balances") or [])
            cny = debts[0] if debts else {}
            return {
                "available_balance": Decimal(str(cny.get("amount", "0"))),
                "credit_granted": Decimal(str(cny.get("credit_amount", "0"))),
                "credit_used": None,
                "currency": cny.get("currency", "CNY"),
            }
        return await asyncio.to_thread(call)

    async def fetch_usage(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        def call():
            headers = self._headers()
            body = json.dumps({
                "region": self.region,
                "project_id": self.project_id,
                "period_type": 2,
                "from_time": start_date.isoformat(),
                "to_time": end_date.isoformat(),
                "limit": 500,
            })
            response = httpx.post(
                f"https://{self.region}.myhuaweicloud.com/v1/{self.project_id}/services/ai-data-records",
                headers=headers, content=body, timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            rows: list[dict[str, Any]] = []
            for item in (payload.get("records") or []):
                rows.append({
                    "usage_date": date.fromisoformat(item.get("date", "")[:10]),
                    "model": item.get("model_name") or item.get("service_name", "pangu"),
                    "input_tokens": int(item.get("input_tokens") or 0),
                    "output_tokens": int(item.get("output_tokens") or 0),
                    "cached_input_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": int(item.get("total_tokens") or 0),
                    "request_count": int(item.get("request_count") or 0),
                })
            return rows
        return await asyncio.to_thread(call)

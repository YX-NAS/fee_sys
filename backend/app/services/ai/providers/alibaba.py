import asyncio
import json
import hmac
import hashlib
import time
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from app.services.ai.providers.base import ProviderAdapter


class AlibabaAdapter(ProviderAdapter):
    capabilities = {"usage": True, "balance": True, "cost": False, "gateway": False}

    def __init__(self, credentials: dict[str, str], base_url: str | None = None):
        self.ak = credentials["access_key_id"]
        self.sk = credentials["secret_access_key"]
        self.base_url = (base_url or "https://dashscope.aliyuncs.com").rstrip("/")

    def _sign(self, method: str, path: str, body: str = "") -> dict[str, str]:
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        now = time.time()
        ts = str(int(now))
        nonce = hashlib.md5(str(now).encode()).hexdigest()[:16]
        sign_str = f"{method}\n{path}\n{ts}\n{nonce}\n{body}"
        signature = hmac.new(
            self.sk.encode(), sign_str.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "Authorization": f"acs {self.ak}:{signature}",
            "X-Acs-Date": ts,
            "X-Acs-Signature-Nonce": nonce,
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> str:
        path = "/api/v1/models"
        headers = self._sign("GET", path)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}{path}", headers=headers,
            )
            response.raise_for_status()
        return "阿里云 DashScope 连接正常"

    async def fetch_balance(self) -> dict[str, Any]:
        path = "/api/v1/usage/overview"
        headers = self._sign("GET", path)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}{path}", headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        overview = (payload.get("data") or {}).get("overview") or {}
        return {
            "available_balance": Decimal(str(overview.get("remaining_quota", "0"))),
            "credit_granted": None,
            "credit_used": None,
            "currency": "CNY",
        }

    async def fetch_usage(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            path = f"/api/v1/usage/statistics?date={current.isoformat()}"
            headers = self._sign("GET", path)
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}{path}", headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
            for item in (payload.get("data") or {}).get("items") or []:
                rows.append({
                    "usage_date": current,
                    "model": item.get("model_name", "dashscope"),
                    "input_tokens": int(item.get("input_tokens") or 0),
                    "output_tokens": int(item.get("output_tokens") or 0),
                    "cached_input_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": int(item.get("total_tokens") or 0),
                    "request_count": int(item.get("request_count") or 0),
                })
            current = current + __import__("datetime").timedelta(days=1)
        return rows

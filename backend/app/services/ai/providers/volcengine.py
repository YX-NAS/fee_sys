import asyncio
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.services.ai.providers.base import ProviderAdapter


class VolcengineAdapter(ProviderAdapter):
    capabilities = {"usage": True, "balance": True, "cost": True, "gateway": False}

    def __init__(self, credentials: dict[str, str], base_url: str | None = None):
        self.credentials = credentials
        self.region = credentials.get("region", "cn-beijing")
        self.host = (base_url or "https://open.volcengineapi.com").rstrip("/")

    def _billing_api(self):
        import volcenginesdkbilling as billing
        from volcenginesdkcore import ApiClient
        from volcenginesdkcore.configuration import Configuration

        configuration = Configuration()
        configuration.ak = self.credentials["access_key_id"]
        configuration.sk = self.credentials["secret_access_key"]
        configuration.region = self.region
        if self.credentials.get("session_token"):
            configuration.session_token = self.credentials["session_token"]
        return billing, billing.BILLINGApi(ApiClient(configuration))

    async def test_connection(self) -> str:
        await self.fetch_balance()
        return "火山引擎连接正常"

    async def fetch_balance(self) -> dict[str, Any]:
        def call():
            billing, api = self._billing_api()
            response = api.query_balance_acct(billing.QueryBalanceAcctRequest())
            return {
                "available_balance": Decimal(str(response.available_balance or "0")),
                "credit_granted": Decimal(str(response.credit_limit or "0")),
                "credit_used": None,
                "currency": "CNY",
            }
        return await asyncio.to_thread(call)

    async def fetch_usage(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        def call():
            from volcenginesdkcore.signv4 import SignerV4

            body = json.dumps({
                "QueryInterval": "Day",
                "StartTime": start_date.isoformat(),
                "EndTime": end_date.isoformat(),
                "Filters": [{"Key": "ModelName", "Values": []}],
            }, separators=(",", ":"))
            query = {"Action": "GetInferenceUsage", "Version": "2024-01-01"}
            headers = {"Host": self.host.split("://", 1)[-1], "Content-Type": "application/json; charset=UTF-8"}
            SignerV4.sign(
                "/", "POST", headers, body, [], query,
                self.credentials["access_key_id"], self.credentials["secret_access_key"],
                self.region, self.credentials.get("ark_signing_service", "ark_stg"),
                self.credentials.get("session_token"),
            )
            response = httpx.post(self.host, params=query, headers=headers, content=body, timeout=60)
            response.raise_for_status()
            payload = response.json()
            if payload.get("ResponseMetadata", {}).get("Error"):
                error = payload["ResponseMetadata"]["Error"]
                raise RuntimeError(f"{error.get('Code')}: {error.get('Message')}")
            result = payload.get("Result") or {}
            field_names = [field["Name"] for field in result.get("Fields", [])]
            rows = []
            for values in result.get("Data", []):
                item = dict(zip(field_names, values))
                rows.append({
                    "usage_date": date.fromisoformat(item["Day"]),
                    "model": item.get("ModelName") or item.get("ModelEndpoint") or "volcengine-ark",
                    "input_tokens": int(item.get("InputTokens") or 0),
                    "output_tokens": int(item.get("OutputTokens") or 0),
                    "cached_input_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": int(item.get("TotalTokens") or 0),
                    "request_count": int(item.get("ReqCnt") or 0),
                })
            return rows
        return await asyncio.to_thread(call)

    async def fetch_cost(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        def call():
            billing, api = self._billing_api()
            totals: dict[tuple[date, str], Decimal] = defaultdict(Decimal)
            currencies: dict[tuple[date, str], str] = {}
            keywords = [v.strip().lower() for v in self.credentials.get(
                "billing_product_keywords", "ark,方舟,大模型"
            ).split(",") if v.strip()]
            month = start_date.replace(day=1)
            while month <= end_date:
                offset, limit = 0, 300
                while True:
                    request = billing.ListAmortizedCostBillDailyRequest(
                        amortized_month=month.strftime("%Y-%m"), amortized_day=None,
                        limit=limit, offset=offset, need_record_num=1,
                    )
                    response = api.list_amortized_cost_bill_daily(request)
                    records = response.list or []
                    for row in records:
                        if not row.amortized_day:
                            continue
                        bill_date = date.fromisoformat(row.amortized_day[:10])
                        if not start_date <= bill_date <= end_date:
                            continue
                        product_text = " ".join(filter(None, [
                            row.product, row.product_zh, row.config_name, row.instance_name,
                        ])).lower()
                        if not product_text or not any(name in product_text for name in keywords):
                            continue
                        model = row.config_name or row.instance_name or row.element or "volcengine-ark-bill"
                        key = (bill_date, model)
                        totals[key] += Decimal(str(row.daily_amortized_payable_amount or row.daily_amortized_paid_amount or "0"))
                        currencies[key] = row.currency or "CNY"
                    offset += len(records)
                    if not records or offset >= int(response.total or 0):
                        break
                month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
            return [
                {"usage_date": day, "model": model, "cost": cost, "currency": currencies[(day, model)]}
                for (day, model), cost in totals.items()
            ]
        return await asyncio.to_thread(call)

from datetime import date
from typing import Any


class ProviderAdapter:
    capabilities: dict[str, bool] = {}

    async def test_connection(self) -> str:
        raise NotImplementedError

    async def fetch_balance(self) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_usage(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        return []

    async def fetch_cost(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        return []

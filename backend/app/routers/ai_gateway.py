import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_models import (
    AIAccountStatus, AIGatewayKey, AIGatewayKeyStatus, AIProvider,
    AIProviderAccount, AIRequestStatus,
)
from app.cache import get_redis
from app.config import get_settings
from app.database import AsyncSessionLocal, get_db
from app.services.ai.monitoring import record_gateway_request
from app.services.ai.pricing import extract_usage
from app.services.ai.credentials import load_default_api_credentials
from app.services.ai.security import hash_gateway_key

router = APIRouter(prefix="/api/ai-gateway/v1", tags=["AI Gateway"])
settings = get_settings()


def _openai_error(message: str, status_code: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": "invalid_request_error", "param": None, "code": code}},
    )


async def _authenticate(
    request: Request, db: AsyncSession = Depends(get_db),
) -> tuple[AIGatewayKey, AIProviderAccount, dict[str, str]]:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Gateway Key")
    plaintext = authorization[7:].strip()
    if not plaintext.startswith("fgw_"):
        raise HTTPException(status_code=401, detail="无效的 Gateway Key")
    key = (await db.execute(select(AIGatewayKey).where(
        AIGatewayKey.key_hash == hash_gateway_key(plaintext),
    ))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not key or key.status != AIGatewayKeyStatus.active or (key.expires_at and key.expires_at <= now):
        raise HTTPException(status_code=401, detail="Gateway Key 无效、已停用或已过期")
    account = (await db.execute(select(AIProviderAccount).where(
        AIProviderAccount.id == key.provider_account_id,
    ))).scalar_one()
    if account.provider != AIProvider.deepseek or account.status == AIAccountStatus.inactive:
        raise HTTPException(status_code=403, detail="关联 DeepSeek 账号不可用")
    try:
        redis = get_redis()
        bucket = f"ai-gateway:rate:{key.id}:{now.strftime('%Y%m%d%H%M')}"
        count = await redis.incr(bucket)
        if count == 1:
            await redis.expire(bucket, 90)
        if count > key.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Gateway Key 请求频率超限")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="网关限流服务暂不可用") from None
    key.last_used_at = now
    await db.flush()
    try:
        credentials = await load_default_api_credentials(db, account)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return key, account, credentials


def _upstream_headers(credentials: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {credentials['api_key']}", "Content-Type": "application/json"}


def _base_url(account: AIProviderAccount) -> str:
    return (account.base_url or settings.DEEPSEEK_BASE_URL).rstrip("/")


async def _persist_request(
    *, account: AIProviderAccount, key: AIGatewayKey, model: str, endpoint: str,
    usage: dict[str, int] | None, request_status: AIRequestStatus, http_status: int | None,
    started: float, provider_request_id: str | None = None, error_code: str | None = None,
) -> None:
    empty = {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    async with AsyncSessionLocal() as db:
        attached_account = (await db.execute(select(AIProviderAccount).where(AIProviderAccount.id == account.id))).scalar_one()
        await record_gateway_request(
            db, account=attached_account, gateway_key_id=key.id, model=model,
            endpoint=endpoint, usage=usage or empty, request_status=request_status,
            http_status=http_status, duration_ms=int((time.monotonic() - started) * 1000),
            provider_request_id=provider_request_id, error_code=error_code,
        )
        await db.commit()


async def _proxy_non_stream(
    account: AIProviderAccount, key: AIGatewayKey, credentials: dict[str, str],
    endpoint: str, payload: dict[str, Any],
) -> Response:
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.AI_PROVIDER_TIMEOUT_SECONDS) as client:
            upstream = await client.post(
                f"{_base_url(account)}{endpoint}", headers=_upstream_headers(credentials), json=payload,
            )
        data = None
        try:
            data = upstream.json()
        except ValueError:
            pass
        usage = extract_usage(data) if upstream.is_success and isinstance(data, dict) and data.get("usage") else None
        await _persist_request(
            account=account, key=key, model=str(payload.get("model", "unknown")), endpoint=endpoint,
            usage=usage, request_status=AIRequestStatus.success if upstream.is_success else AIRequestStatus.failed,
            http_status=upstream.status_code, started=started,
            provider_request_id=data.get("id") if isinstance(data, dict) else None,
            error_code=((data.get("error") or {}).get("code") if isinstance(data, dict) else None),
        )
        headers = {}
        if upstream.headers.get("x-request-id"):
            headers["x-request-id"] = upstream.headers["x-request-id"]
        return Response(
            content=upstream.content, status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"), headers=headers,
        )
    except httpx.TimeoutException:
        await _persist_request(
            account=account, key=key, model=str(payload.get("model", "unknown")), endpoint=endpoint,
            usage=None, request_status=AIRequestStatus.failed, http_status=504, started=started, error_code="upstream_timeout",
        )
        return _openai_error("DeepSeek 请求超时", 504, "upstream_timeout")
    except httpx.RequestError:
        await _persist_request(
            account=account, key=key, model=str(payload.get("model", "unknown")), endpoint=endpoint,
            usage=None, request_status=AIRequestStatus.failed, http_status=502, started=started, error_code="upstream_unavailable",
        )
        return _openai_error("DeepSeek 服务暂不可用", 502, "upstream_unavailable")


async def _proxy_stream(
    account: AIProviderAccount, key: AIGatewayKey, credentials: dict[str, str],
    endpoint: str, payload: dict[str, Any],
) -> Response:
    payload["stream_options"] = {**(payload.get("stream_options") or {}), "include_usage": True}
    started = time.monotonic()
    client = httpx.AsyncClient(timeout=settings.AI_PROVIDER_TIMEOUT_SECONDS)
    request = client.build_request(
        "POST", f"{_base_url(account)}{endpoint}",
        headers=_upstream_headers(credentials), json=payload,
    )
    try:
        upstream = await client.send(request, stream=True)
    except httpx.RequestError:
        await client.aclose()
        await _persist_request(
            account=account, key=key, model=str(payload.get("model", "unknown")), endpoint=endpoint,
            usage=None, request_status=AIRequestStatus.failed, http_status=502, started=started, error_code="upstream_unavailable",
        )
        return _openai_error("DeepSeek 服务暂不可用", 502, "upstream_unavailable")
    if not upstream.is_success:
        content = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        await _persist_request(
            account=account, key=key, model=str(payload.get("model", "unknown")), endpoint=endpoint,
            usage=None, request_status=AIRequestStatus.failed, http_status=upstream.status_code,
            started=started, error_code="provider_error",
        )
        return Response(content=content, status_code=upstream.status_code, media_type=upstream.headers.get("content-type", "application/json"))

    async def stream() -> AsyncIterator[bytes]:
        usage = None
        provider_request_id = None
        completed = False
        try:
            async for line in upstream.aiter_lines():
                wire = f"{line}\n".encode()
                yield wire
                if line.startswith("data: "):
                    raw = line[6:]
                    if raw == "[DONE]":
                        completed = True
                    else:
                        try:
                            chunk = json.loads(raw)
                            provider_request_id = provider_request_id or chunk.get("id")
                            if chunk.get("usage"):
                                usage = extract_usage(chunk)
                        except (ValueError, TypeError):
                            pass
        finally:
            await upstream.aclose()
            await client.aclose()
            try:
                await _persist_request(
                    account=account, key=key, model=str(payload.get("model", "unknown")), endpoint=endpoint,
                    usage=usage,
                    request_status=AIRequestStatus.success if completed and usage is not None else AIRequestStatus.incomplete,
                    http_status=upstream.status_code, started=started, provider_request_id=provider_request_id,
                    error_code=None if completed and usage is not None else "missing_usage",
                )
            except Exception:
                # The provider stream has already completed; accounting failure
                # is surfaced through sync monitoring instead of corrupting SSE.
                pass

    return StreamingResponse(stream(), status_code=upstream.status_code, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _handle_completion(
    request: Request, endpoint: str,
    auth: tuple[AIGatewayKey, AIProviderAccount, dict[str, str]],
) -> Response:
    key, account, credentials = auth
    try:
        payload = await request.json()
    except ValueError:
        return _openai_error("请求体必须是 JSON", 400, "invalid_json")
    if not isinstance(payload, dict) or not payload.get("model"):
        return _openai_error("缺少 model 参数", 400, "missing_model")
    if payload.get("stream"):
        return await _proxy_stream(account, key, credentials, endpoint, payload)
    return await _proxy_non_stream(account, key, credentials, endpoint, payload)


@router.post("/chat/completions")
async def chat_completions(request: Request, auth=Depends(_authenticate)):
    return await _handle_completion(request, "/chat/completions", auth)


@router.post("/completions")
async def completions(request: Request, auth=Depends(_authenticate)):
    return await _handle_completion(request, "/completions", auth)


@router.get("/models")
async def models(auth=Depends(_authenticate)):
    _, account, credentials = auth
    async with httpx.AsyncClient(timeout=20) as client:
        upstream = await client.get(
            f"{_base_url(account)}/models", headers=_upstream_headers(credentials)
        )
    return Response(content=upstream.content, status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type", "application/json"))


@router.api_route("/{unsupported_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def unsupported(unsupported_path: str):
    return _openai_error(f"网关暂不支持 /{unsupported_path}", 404, "unsupported_endpoint")

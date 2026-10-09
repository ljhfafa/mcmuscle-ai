from __future__ import annotations

import asyncio
import copy
import json
import time
from contextlib import asynccontextmanager
from datetime import timedelta

READ_TOOLS = frozenset(
    {
        "list-nutrition-foods",
        "query-nearby-stores",
        "delivery-query-addresses",
        "delivery-query-stores",
        "query-meals",
        "query-meal-detail",
        "available-coupons",
        "query-my-coupons",
        "query-store-coupons",
        "calculate-price",
        "query-order",
    }
)
WRITE_TOOLS = frozenset({"auto-bind-coupons", "create-order"})


class MCPFailure(RuntimeError):
    pass


class AuthenticationFailure(MCPFailure):
    pass


class AmbiguousMutation(MCPFailure):
    pass


class RateLimiter:
    """Serial 0.25s minimum interval => <=240 calls/min per client (official ceiling: 600)."""

    def __init__(self, interval=0.25):
        self.interval, self.next = interval, 0.0
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            await asyncio.sleep(max(0, self.next - time.monotonic()))
            self.next = time.monotonic() + self.interval


def status(exc):
    if hasattr(exc, "exceptions"):
        return next((status(e) for e in exc.exceptions if status(e)), None)
    return getattr(getattr(exc, "response", None), "status_code", None)


class Gateway:
    def __init__(self, session, schemas: dict, *, live: bool, timeout=30, sleep=asyncio.sleep):
        self.session, self.schemas, self.live = session, schemas, live
        self.timeout, self.sleep = timeout, sleep
        self.limiter = RateLimiter()
        self.cache: dict = {}
        self.calls = 0

    async def read(self, name: str, arguments: dict, *, fresh=False):
        if name not in READ_TOOLS:
            raise MCPFailure("不在只读工具白名单")
        ttl = (
            3600
            if name == "list-nutrition-foods"
            else 30
            if name in ("query-meals", "query-meal-detail")
            else 0
        )
        key = (name, json.dumps(arguments, sort_keys=True))
        hit = self.cache.get(key)
        if not fresh and ttl and hit and time.monotonic() - hit[0] < ttl:
            return copy.deepcopy(hit[1])
        result = await self._call(name, arguments, mutation=False)
        if ttl:
            self.cache[key] = (time.monotonic(), copy.deepcopy(result))
        return result

    async def claim_coupons(self, *, explicitly_authorized=False):
        if not explicitly_authorized:
            raise MCPFailure("领取优惠券需要用户明确授权")
        return await self._call("auto-bind-coupons", {}, mutation=True)

    async def _create_order(self, arguments: dict):
        # Internal primitive; application entrypoint is ordering.OrderService only.
        return await self._call("create-order", arguments, mutation=True)

    async def _call(self, name, arguments, *, mutation):
        from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

        if name not in READ_TOOLS | WRITE_TOOLS or name not in self.schemas:
            raise MCPFailure("工具不存在或未获允许")
        try:
            Draft202012Validator(self.schemas[name]).validate(arguments)
        except Exception:
            raise MCPFailure("参数不符合服务器实时 schema；请重新查询工具定义") from None
        for attempt in range(1 if mutation else 3):
            await self.limiter.wait()
            self.calls += 1
            try:
                result = await asyncio.wait_for(
                    self.session.call_tool(name, arguments), self.timeout
                )
                if getattr(result, "isError", False):
                    raise MCPFailure("MCP 工具返回业务错误；未输出可能含隐私的原文")
                return result
            except MCPFailure:
                raise
            except Exception as e:
                code = status(e)
                if code == 401:
                    raise AuthenticationFailure(
                        "401：新 Token 无效/过期，请在本机重新配置"
                    ) from None
                if mutation:
                    raise AmbiguousMutation(
                        "操作结果不明确：禁止重试；请查询订单/账户状态"
                    ) from None
                import httpx

                retryable = code in (429, 500, 502, 503, 504) or isinstance(
                    e, (TimeoutError, httpx.TransportError)
                )
                if not retryable or attempt == 2:
                    raise MCPFailure("只读 MCP 请求失败；请检查网络、权限或接口状态") from None
                delay = 2**attempt
                try:
                    response = getattr(e, "response", None)
                    if response is not None:
                        delay = min(60, max(delay, float(response.headers.get("Retry-After", 0))))
                except (AttributeError, ValueError):
                    pass
                await self.sleep(delay)
        raise MCPFailure("重试次数耗尽")


@asynccontextmanager
async def connect():
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from mcmuscle.mcp.credentials import token

    # Fixed official origin. Never redirect an Authorization header elsewhere.
    async with httpx.AsyncClient(
        headers={"Authorization": "Bearer " + token()}, timeout=30, follow_redirects=False
    ) as http:
        async with streamable_http_client("https://mcp.mcd.cn", http_client=http) as (
            read,
            write,
            _,
        ):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=30)
            ) as session:
                await session.initialize()
                schemas, cursor = {}, None
                for _ in range(20):
                    page = await session.list_tools(cursor=cursor)
                    schemas.update({t.name: t.inputSchema for t in page.tools})
                    cursor = page.nextCursor
                    if not cursor:
                        break
                else:
                    raise MCPFailure("工具目录分页异常")
                yield Gateway(session, schemas, live=True)

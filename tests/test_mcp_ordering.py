import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from mcmuscle.demo import menu
from mcmuscle.mcp.client import AmbiguousMutation, AuthenticationFailure, Gateway, MCPFailure
from mcmuscle.mcp.pricing import Price, parse_price, verify_candidates
from mcmuscle.mcp.workflow import official_price
from mcmuscle.models import Constraints, Profile
from mcmuscle.nutrition.engine import targets
from mcmuscle.optimizer.engine import search
from mcmuscle.ordering.service import OrderPlan, OrderService


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        r = self.responses.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


async def no_sleep(_):
    pass


def gateway(responses, tool="list-nutrition-foods"):
    g = Gateway(FakeSession(responses), {tool: {"type": "object"}}, live=False, sleep=no_sleep)
    g.limiter.interval = 0
    return g


def ok():
    return SimpleNamespace(isError=False, structuredContent={"success": True, "data": []})


def http_error(code):
    return httpx.HTTPStatusError(
        "private detail should not leak",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(code, headers={"Retry-After": "0"}),
    )


def test_auth_failure_no_retry():
    g = gateway([http_error(401), ok()])
    with pytest.raises(AuthenticationFailure, match="401"):
        asyncio.run(g.read("list-nutrition-foods", {}))
    assert len(g.session.calls) == 1


@pytest.mark.parametrize(
    "error", [http_error(429), http_error(503), TimeoutError(), httpx.ConnectError("secret")]
)
def test_retry_read_only(error):
    g = gateway([error, ok()])
    asyncio.run(g.read("list-nutrition-foods", {}))
    assert len(g.session.calls) == 2


def test_retry_exhausted_redaction():
    g = gateway([TimeoutError("private")] * 3)
    with pytest.raises(MCPFailure) as e:
        asyncio.run(g.read("list-nutrition-foods", {}))
    assert "private" not in str(e.value) and len(g.session.calls) == 3


def test_tool_error_no_retry():
    g = gateway([SimpleNamespace(isError=True)])
    with pytest.raises(MCPFailure):
        asyncio.run(g.read("list-nutrition-foods", {}))
    assert len(g.session.calls) == 1


def test_cache():
    async def run():
        g = gateway([ok()])
        await g.read("list-nutrition-foods", {})
        await g.read("list-nutrition-foods", {})
        assert len(g.session.calls) == 1

    asyncio.run(run())


def test_schema_and_unknown_tool():
    g = gateway([])
    g.schemas["list-nutrition-foods"] = {"type": "object", "required": ["id"]}
    with pytest.raises(MCPFailure):
        asyncio.run(g.read("list-nutrition-foods", {}))
    with pytest.raises(MCPFailure):
        asyncio.run(g.read("draw-lottery", {}))
    assert not g.session.calls


def test_coupon_explicit_authorization():
    g = gateway([ok()], "auto-bind-coupons")
    with pytest.raises(MCPFailure):
        asyncio.run(g.claim_coupons())
    asyncio.run(g.claim_coupons(explicitly_authorized=True))
    assert len(g.session.calls) == 1


def test_mutation_never_retried():
    g = gateway([TimeoutError(), ok()], "create-order")
    with pytest.raises(AmbiguousMutation):
        asyncio.run(g._create_order({}))
    assert len(g.session.calls) == 1


def test_price_units_and_reconcile():
    p = official_price({"price": 3350, "originalPrice": 3500, "discount": 150})
    assert p.total_fen == 3350 and p.discount_fen == 150 and p.delivery_fen == 0
    p = parse_price(
        {"t": "30.5", "o": "35", "d": "5", "f": "0.5"},
        dict(total="t", original="o", discount="d", delivery="f"),
        unit="yuan",
    )
    assert p.total_fen == 3050
    with pytest.raises(ValueError):
        official_price({"price": 3300, "originalPrice": 3500, "discount": 150})
    with pytest.raises(ValueError):
        official_price({"price": 3300, "originalPrice": 3500, "discount": 200}, delivery=True)


def test_coupon_can_make_overbudget_feasible():
    p = Profile(budget=10, weight_kg=75)
    c = Constraints(max_items=1)
    candidates = search(menu()[:1], p, c, allow_over_budget=True).candidates

    async def quote(x):
        return Price(900, 1800, 900, 0)

    results, stats = asyncio.run(
        verify_candidates(candidates, p, targets(p), c, quote, max_calls=1)
    )
    assert results["protein"].price_fen == 900 and stats["quoted"] == 1


def test_quote_failure_never_fakes_price():
    p = Profile(budget=40)
    c = Constraints()

    async def quote(x):
        raise MCPFailure("failed")

    results, stats = asyncio.run(
        verify_candidates(search(menu(), p, c).candidates, p, targets(p), c, quote, max_calls=2)
    )
    assert not results and stats["failures"] == 2


def plan(**updates):
    args = {
        "storeCode": "mock-store",
        "orderType": 1,
        "beType": 1,
        "takeWayCode": "eat-in",
        "items": [{"productCode": "mock-item", "quantity": 1}],
    }
    values = dict(
        store="mock-store",
        method="pickup",
        items=(("mock-item", 1),),
        total_fen=1000,
        quoted_at=100,
        quote_evidence="mock-price-evidence",
        arguments_json=json.dumps(args),
    )
    return OrderPlan(**(values | updates))


def test_unconfirmed_blocked(tmp_path):
    g = gateway([], "create-order")
    s = OrderService(g, tmp_path / "journal", clock=lambda: 100)
    with pytest.raises(ValueError):
        asyncio.run(s.create(plan(), "推荐一下"))
    assert not g.session.calls


def test_confirmed_exact_parameters_and_durable_replay(tmp_path):
    g = gateway([ok()], "create-order")
    p = plan()
    journal = tmp_path / "journal"
    s = OrderService(g, journal, clock=lambda: 100)
    asyncio.run(s.create(p, "确认下单 " + p.digest()[:12]))
    assert g.session.calls[0][1] == json.loads(p.arguments_json)
    s2 = OrderService(g, journal, clock=lambda: 100)
    with pytest.raises(ValueError):
        asyncio.run(s2.create(p, "确认下单 " + p.digest()[:12]))
    assert len(g.session.calls) == 1


@pytest.mark.parametrize("age", [-1, 121])
def test_expired_or_future_confirmation(tmp_path, age):
    g = gateway([], "create-order")
    p = plan()
    s = OrderService(g, tmp_path / "journal", clock=lambda: 100 + age)
    with pytest.raises(ValueError):
        asyncio.run(s.create(p, "确认下单 " + p.digest()[:12]))
    assert not g.session.calls


def test_changed_price_requires_reconfirmation(tmp_path):
    p = plan()
    changed = plan(total_fen=1200)
    g = gateway([], "create-order")
    with pytest.raises(ValueError):
        asyncio.run(
            OrderService(g, tmp_path / "j", clock=lambda: 100).create(
                changed, "确认下单 " + p.digest()[:12]
            )
        )


def test_test_mode_rejects_real_client(tmp_path):
    g = gateway([])
    g.live = True
    with pytest.raises(ValueError):
        OrderService(g, tmp_path / "j")


def test_order_exception_consumes_confirmation(tmp_path):
    p = plan()
    g = gateway([TimeoutError(), ok()], "create-order")
    s = OrderService(g, tmp_path / "j", clock=lambda: 100)
    with pytest.raises(AmbiguousMutation):
        asyncio.run(s.create(p, "确认下单 " + p.digest()[:12]))
    with pytest.raises(ValueError):
        asyncio.run(s.create(p, "确认下单 " + p.digest()[:12]))
    assert len(g.session.calls) == 1


def test_mismatched_order_summary_rejected(tmp_path):
    p = plan(store="other-store")
    g = gateway([], "create-order")
    with pytest.raises(ValueError):
        asyncio.run(
            OrderService(g, tmp_path / "j", clock=lambda: 100).create(
                p, "确认下单 " + p.digest()[:12]
            )
        )


def test_prepare_mock_order(tmp_path):
    from mcmuscle.ordering.prepare import prepare

    price = {
        "price": 1000,
        "originalPrice": 1000,
        "discount": 0,
        "productList": [{"productCode": "mock-item", "quantity": 1}],
        "takeWayList": [{"code": "eat-in"}],
    }
    g = gateway(
        [SimpleNamespace(isError=False, structuredContent={"success": True, "data": price})],
        "calculate-price",
    )
    p = asyncio.run(
        prepare(
            g,
            {"storeCode": "mock-store", "orderType": 1, "beType": 1},
            [{"productCode": "mock-item", "quantity": 1}],
            take_way="eat-in",
            clock=lambda: 100,
        )
    )
    assert p.total_fen == 1000 and p.mode == "mock"


def test_observed_delivery_fees_not_double_counted():
    data = {
        "productOriginalPrice": 2500,
        "productPrice": 2500,
        "deliveryOriginalPrice": 600,
        "deliveryPrice": 600,
        "packingOriginalPrice": 110,
        "packingPrice": 110,
        "originalPrice": 3210,
        "discount": 0,
        "price": 3210,
    }
    p = official_price(data, delivery=True)
    assert p.total_fen == 3210 and p.delivery_fen == 600 and p.packing_fen == 110
    with pytest.raises(ValueError):
        official_price({**data, "packingPrice": 0}, delivery=True)

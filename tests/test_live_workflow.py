import asyncio
from types import SimpleNamespace

import pytest

from mcmuscle.cli import main
from mcmuscle.demo import menu
from mcmuscle.mcp.menu import valid_store
from mcmuscle.mcp.official import Official
from mcmuscle.mcp.workflow import recommend_live
from mcmuscle.models import Profile
from mcmuscle.nutrition.engine import targets
from mcmuscle.optimizer.engine import rank, search
from mcmuscle.presentation import render


class FakeGateway:
    live = False

    def __init__(self):
        self.calls = []

    async def read(self, name, args, **kwargs):
        self.calls.append((name, args))
        data = {
            "list-nutrition-foods": "[1]{productName,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n  MOCK A,400,25,12,40,400,80",
            "query-meals": {
                "categories": [{"meals": [{"code": "mock-a"}]}],
                "meals": {
                    "mock-a": {"name": "MOCK A", "currentPrice": "12.5", "canWithOrder": False}
                },
            },
            "query-meal-detail": {"code": "mock-a", "rounds": []},
            "query-nearby-stores": [{"storeCode": "mock-store", "businessStatus": True}],
            "delivery-query-addresses": [],
            "delivery-query-stores": [],
            "available-coupons": [],
            "query-my-coupons": {"coupons": []},
            "query-store-coupons": [],
            "query-order": {"status": "MOCK"},
        }
        if name == "calculate-price":
            total = sum(i["quantity"] * 1250 for i in args["items"])
            payload = {"price": total, "originalPrice": total, "discount": 0}
        else:
            payload = data[name]
        return SimpleNamespace(
            isError=False, structuredContent={"success": True, "code": 200, "data": payload}
        )


def test_live_workflow_with_fake_transport():
    g = FakeGateway()
    p = Profile(budget=30, weight_kg=70)
    result, t, stats, _ = asyncio.run(
        recommend_live(
            g, p, {"businessStatus": True}, Official.context("mock-store"), quote_limit=2
        )
    )
    assert result["protein"].nutrition.protein_g == 50
    assert result["protein"].price_fen == 2500 and result["protein"].quoted
    assert stats["verified_menu_items"] == 1
    assert all(n != "create-order" for n, _ in g.calls)
    rendered = render(result, p, t, mock=True, scope="test")
    assert "MOCK DEMO" in rendered and "钠" in rendered and "配送费" in rendered


def test_missing_allergy_data_excludes_live_items():
    g = FakeGateway()
    p = Profile(budget=30, allergies=("milk",))
    result, _, _, _ = asyncio.run(
        recommend_live(g, p, {"businessStatus": True}, Official.context("mock-store"))
    )
    assert not result


def test_official_adapters():
    async def run():
        g = FakeGateway()
        a = Official(g)
        c = a.context("mock-store")
        assert await a.nearby("MOCK city", "MOCK square")
        assert await a.addresses() == []
        assert await a.delivery_stores("MOCK address") == []
        assert len(await a.coupons(c)) == 3
        assert (await a.order_status("mock-order"))["status"] == "MOCK"

    asyncio.run(run())


def test_pickup_omits_be_code_and_reservation():
    assert "beCode" not in Official.context("s", be_code="ignored")
    assert Official.context("s", delivery=True, be_code="b")["beCode"] == "b"
    with pytest.raises(ValueError):
        Official.context("s", delivery=True)
    with pytest.raises(ValueError):
        Official.context("s", reservation="tomorrow")
    with pytest.raises(ValueError):
        valid_store({"businessStatus": False})
    with pytest.raises(ValueError):
        valid_store({"reservation": False}, "2026-10-10 12:00")
    valid_store(
        {"reservation": True, "reservationTimeOptions": [{"date": "2026-10-10"}]},
        "2026-10-10 12:00",
    )


def test_display_no_false_calorie_claim():
    p = Profile(goal="cut", budget=30, weight_kg=65)
    t = targets(p)
    text = render(rank(search(menu(), p).candidates, p, t), p, t, mock=True, scope="test")
    assert "不能判断方案符合减脂热量控制" in text
    assert "没有找到" in render({}, p, t, mock=True, scope="test")


def test_cli_in_process(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["mcmuscle", "demo"])
    main()
    assert "MOCK DEMO" in capsys.readouterr().out

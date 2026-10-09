import asyncio
from types import SimpleNamespace

from mcmuscle.mcp.coupons import compare_coupon_options


class Fake:
    live = False

    def __init__(self):
        self.calls = []

    async def read(self, name, args, **kwargs):
        self.calls.append((name, args))
        selected = [i for i in args["items"] if i.get("couponId")]
        assert len(selected) <= 1
        total = {"A": 1500, "B": 1700}.get(selected[0]["couponId"], 2000) if selected else 2000
        return SimpleNamespace(
            isError=False,
            structuredContent={
                "success": True,
                "data": {"originalPrice": 2000, "discount": 2000 - total, "price": total},
            },
        )


def test_coupon_official_comparison_no_stacking_or_claim():
    g = Fake()
    apps = [{"item_index": 0, "couponId": c, "couponCode": c} for c in ("A", "B")]
    (price, items, _), stats = asyncio.run(
        compare_coupon_options(
            g,
            {"storeCode": "mock", "beType": 1, "orderType": 1},
            [{"productCode": "mock", "quantity": 1}],
            apps,
            max_calls=3,
        )
    )
    assert price.total_fen == 1500 and items[0]["couponId"] == "A" and stats["calls"] == 3
    assert all(name == "calculate-price" for name, _ in g.calls)

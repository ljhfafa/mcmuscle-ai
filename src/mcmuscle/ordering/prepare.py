import hashlib
import json
import time

from mcmuscle.mcp.official import Official
from mcmuscle.mcp.workflow import official_price
from mcmuscle.ordering.service import OrderPlan


async def prepare(
    gateway,
    context,
    items,
    *,
    take_way=None,
    address_id=None,
    address_display=None,
    tableware=False,
    clock=time.time,
):
    if context["orderType"] not in (1, 2) or context["beType"] not in (1, 2):
        raise ValueError("只支持到店自取和麦乐送")
    quote = await Official(gateway).quote(context, items, tableware=tableware)
    price = official_price(quote, delivery=context["orderType"] == 2)
    # Reconcile priced products to requested products before asking confirmation.
    expected = sorted((i["productCode"], i["quantity"]) for i in items)
    actual = sorted((i["productCode"], i["quantity"]) for i in quote.get("productList", []))
    if actual != expected:
        raise ValueError("算价餐品与选择不一致")
    args = {**context, "items": items, "needTableware": tableware}
    if context["orderType"] == 1:
        if take_way not in {w["code"] for w in quote.get("takeWayList", [])}:
            raise ValueError("请选择官方提供的堂食/外带方式")
        args["takeWayCode"] = take_way
    else:
        if not address_id or not address_display:
            raise ValueError("请确认配送地址")
        args["addressId"] = address_id
    coupons = tuple(sorted(str(i["couponId"]) for i in items if i.get("couponId")))
    return OrderPlan(
        store=context["storeCode"],
        method="delivery" if context["orderType"] == 2 else "pickup",
        address=address_display,
        items=tuple(expected),
        coupons=coupons,
        total_fen=price.total_fen,
        quoted_at=clock(),
        quote_evidence=hashlib.sha256(json.dumps(quote, sort_keys=True).encode()).hexdigest(),
        arguments_json=json.dumps(args, sort_keys=True),
        mode="live" if gateway.live else "mock",
    )

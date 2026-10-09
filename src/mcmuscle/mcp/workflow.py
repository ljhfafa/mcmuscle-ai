"""Live bounded recommendation: current store -> catalog -> menu -> detail -> official quotes."""

from mcmuscle.mcp.menu import menu_items, valid_store
from mcmuscle.mcp.official import Official
from mcmuscle.mcp.pricing import verify_candidates
from mcmuscle.models import Constraints
from mcmuscle.nutrition.engine import targets
from mcmuscle.optimizer.engine import search


def official_price(data, *, delivery=False):
    """Observed amounts are integer fen; originalPrice already includes all original fees."""
    from mcmuscle.mcp.pricing import Price

    required = {"price", "originalPrice", "discount"}
    if delivery:
        required |= {
            "productOriginalPrice",
            "productPrice",
            "deliveryOriginalPrice",
            "deliveryPrice",
            "packingOriginalPrice",
            "packingPrice",
        }
    if not required <= data.keys():
        raise ValueError("费用字段不完整，停止算价")
    fields = required | ({"productOriginalPrice", "productPrice"} & data.keys())
    if any(type(data[k]) is not int or data[k] < 0 for k in fields):
        raise ValueError("官方金额必须为非负整数分")
    delivery_fee = data.get("deliveryPrice", 0)
    packing_fee = data.get("packingPrice", 0)
    if data["originalPrice"] - data["discount"] != data["price"]:
        raise ValueError("官方折扣与总价不一致")
    if delivery:
        if (
            data["productOriginalPrice"]
            + data["deliveryOriginalPrice"]
            + data["packingOriginalPrice"]
            != data["originalPrice"]
        ):
            raise ValueError("原价费用组成不一致")
        if data["productPrice"] + delivery_fee + packing_fee != data["price"]:
            raise ValueError("实付费用组成不一致")
    return Price(
        data["price"],
        data["originalPrice"],
        data["discount"],
        delivery_fee,
        packing_fen=packing_fee,
    )


async def recommend_live(
    gateway,
    profile,
    store,
    context,
    *,
    quote_limit=6,
    item_limit=24,
    constraints=None,
    coupon_items=None,
):
    valid_store(store, context.get("reservationDate"))
    api = Official(gateway)
    foods, issues = await api.nutrition()
    menu = await api.menu(context)
    items, rejected = menu_items(menu, foods)
    # Bounded diversification; explicit scope includes menu truncation.
    items = sorted(items, key=lambda i: (-i.nutrition.protein_g / max(i.price_fen, 1), i.id))[
        :item_limit
    ]
    verified_items = []
    details = {}
    for item in items:
        detail = await api.detail(context, item.id)
        if detail.get("code") != item.id or detail.get("rounds"):
            continue
        details[item.id] = detail
        verified_items.append(item)
    t = targets(profile)
    c = constraints or Constraints(
        max_kcal=t.meal_kcal[1] if profile.goal == "cut" and t.meal_kcal else None
    )
    space = search(verified_items, profile, c, allow_over_budget=True)
    quoted = {}

    async def quote(combo):
        args = []
        for item, q in combo.lines:
            row = {"productCode": item.id, "quantity": q}
            # Only explicitly selected coupons from current store response; server validates eligibility.
            if coupon_items and item.id in coupon_items:
                coupon = coupon_items[item.id]
                row.update({k: coupon[k] for k in ("couponId", "couponCode") if k in coupon})
            args.append(row)
        data = await api.quote(context, args)
        price = official_price(data, delivery=context["orderType"] == 2)
        quoted[combo.key] = {"data": data, "items": args}
        return price

    results, stats = await verify_candidates(
        space.candidates, profile, t, c, quote, max_calls=quote_limit
    )
    return (
        results,
        t,
        {
            **stats,
            "catalog_issues": len(issues),
            "unmatched_menu_items": len(rejected),
            "verified_menu_items": len(verified_items),
            "search_exhaustive": space.exhaustive,
            "search_scope": space.scope,
        },
        quoted,
    )

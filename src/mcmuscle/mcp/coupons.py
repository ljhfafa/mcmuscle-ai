"""Bounded official quote comparison for explicit coupon applications; never claims coupons."""

import copy

from mcmuscle.mcp.official import Official
from mcmuscle.mcp.workflow import official_price


async def compare_coupon_options(gateway, context, items, applications, *, max_calls=6):
    """applications: iterable of {item_index, couponId, couponCode} from verified store coupons.

    Baseline + one coupon at a time, never assumed stacking. Server remains authoritative.
    Returned payload can be passed to prepare(), which re-quotes before confirmation.
    """
    if not 1 <= max_calls <= 20:
        raise ValueError("优惠报价次数必须为1至20")
    api = Official(gateway)
    variants = [copy.deepcopy(items)]
    for app in applications:
        if len(variants) >= max_calls:
            break
        index = app["item_index"]
        if type(index) is not int or not 0 <= index < len(items):
            raise ValueError("优惠券应用商品不存在")
        if not app.get("couponId") or not app.get("couponCode"):
            raise ValueError("优惠券编码缺失")
        variant = copy.deepcopy(items)
        # Every variant starts with no coupon to avoid silently stacking existing applications.
        for item in variant:
            item.pop("couponId", None)
            item.pop("couponCode", None)
        variant[index].update({"couponId": app["couponId"], "couponCode": app["couponCode"]})
        if variant not in variants:
            variants.append(variant)
    for item in variants[0]:
        item.pop("couponId", None)
        item.pop("couponCode", None)
    options = []
    errors = 0
    for variant in variants:
        try:
            response = await api.quote(context, variant)
            price = official_price(response, delivery=context["orderType"] == 2)
            options.append((price, variant, response))
        except (ValueError, RuntimeError):
            errors += 1
    if not options:
        raise ValueError("所有候选官方报价失败，不能推断优惠价格")
    return min(options, key=lambda option: option[0].total_fen), {
        "calls": len(variants),
        "failures": errors,
    }

from dataclasses import dataclass

from mcmuscle.models import Constraints, Profile, Targets, fen
from mcmuscle.optimizer.engine import Combination, apply_price, feasible, rank


@dataclass(frozen=True)
class Price:
    total_fen: int
    original_fen: int
    discount_fen: int
    delivery_fen: int
    source: str = "calculate-price"
    packing_fen: int = 0


def parse_price(data: dict, fields: dict[str, str], *, unit: str) -> Price:
    """Explicit observed-field mapping; original means goods before discount, excludes delivery."""
    if unit not in ("yuan", "fen") or set(fields) != {"total", "original", "discount", "delivery"}:
        raise ValueError("算价字段/货币单位必须明确")
    values = {}
    for key, field in fields.items():
        value = data[field]
        if isinstance(value, bool):
            raise ValueError("非法金额")
        if unit == "yuan":
            values[key] = fen(value)
        else:
            values[key] = int(value)
            if values[key] < 0 or str(values[key]) != str(value):
                raise ValueError("分必须为非负整数")
    if values["original"] - values["discount"] + values["delivery"] != values["total"]:
        raise ValueError("官方价格组成不一致；停止下单，核对算价 schema")
    return Price(
        values["total"],
        values["original"] + values["delivery"],
        values["discount"],
        values["delivery"],
    )


async def verify_candidates(
    candidates: list[Combination],
    p: Profile,
    t: Targets,
    constraints: Constraints,
    quote,
    *,
    max_calls=9,
):
    """quote(combination)->Price is an adapter over the observed calculate-price schema.
    Coupon stacking/eligibility are server-owned. Never infer a discount from a coupon name.
    """
    if not 1 <= max_calls <= 30:
        raise ValueError("算价调用上限须为1到30")
    pool = list(candidates)
    shortlist: list[Combination] = []
    while pool and len(shortlist) < max_calls:
        choices = rank(pool, p, t)
        for x in choices.values():
            if x not in shortlist and len(shortlist) < max_calls:
                shortlist.append(x)
        selected = {x.key for x in shortlist}
        pool = [x for x in pool if x.key not in selected]
    verified = []
    failures = 0
    for x in shortlist:
        try:
            price = await quote(x)
            if not isinstance(price, Price):
                raise ValueError("未返回已验证价格结构")
            if feasible(x.nutrition, price.total_fen, p, constraints):
                verified.append(
                    apply_price(
                        x,
                        price.total_fen,
                        price.source,
                        original_fen=price.original_fen,
                        discount_fen=price.discount_fen,
                        delivery_fen=price.delivery_fen,
                        packing_fen=price.packing_fen,
                    )
                )
        except (ValueError, RuntimeError):
            failures += 1
    return rank(verified, p, t), {
        "quoted": len(shortlist),
        "failures": failures,
        "scope": "仅在已官方算价的候选中比较；不保证所有券/组合全局最优",
    }

from __future__ import annotations

from dataclasses import dataclass, replace

from mcmuscle.models import Constraints, Item, Nutrients, Profile, Targets, fen


@dataclass(frozen=True)
class Combination:
    lines: tuple[tuple[Item, int], ...]
    nutrition: Nutrients
    price_fen: int
    price_source: str
    quoted: bool = False
    original_fen: int | None = None
    discount_fen: int | None = None
    delivery_fen: int | None = None
    packing_fen: int | None = None

    @property
    def key(self):
        return tuple((i.id, q) for i, q in self.lines)

    def metrics(self, t: Targets) -> dict:
        n, cost = self.nutrition, self.price_fen / 100
        return {
            "yuan_per_protein_g": cost / n.protein_g if n.protein_g else None,
            "protein_per_100_kcal": n.protein_g / n.kcal * 100 if n.kcal else None,
            "protein_per_100_yuan": n.protein_g / cost * 100 if cost else None,
            "kcal_deviation": n.kcal - sum(t.meal_kcal) / 2 if t.meal_kcal else None,
            "protein_target_ratio": n.protein_g / t.meal_protein_g[0] if t.meal_protein_g else None,
        }


@dataclass
class SearchResult:
    candidates: list[Combination]
    exhaustive: bool
    visited: int
    excluded_items: int
    scope: str


def feasible(n: Nutrients, price: int, p: Profile, c: Constraints) -> bool:
    return (
        price <= fen(p.budget)
        and n.kcal >= c.min_kcal
        and (c.max_kcal is None or n.kcal <= c.max_kcal)
        and n.protein_g >= c.min_protein_g
        and (c.max_fat_g is None or n.fat_g <= c.max_fat_g)
        and (c.max_carbs_g is None or n.carbs_g <= c.max_carbs_g)
    )


def search(
    items: list[Item],
    p: Profile,
    c: Constraints | None = None,
    *,
    allow_over_budget: bool = False,
) -> SearchResult:
    c = c or Constraints()
    if len({i.id for i in items}) != len(items):
        raise ValueError("菜单存在重复商品编码")
    eligible = []
    for i in items:
        labels = set(i.tags) | set(i.allergens)
        if not i.available or i.customized:
            continue
        if p.allergies and (not i.allergens_verified or set(p.allergies) & labels):
            continue
        if p.excludes and (not i.ingredients_verified or set(p.excludes) & labels):
            continue
        eligible.append(i)
    eligible.sort(key=lambda i: i.id)
    found: list[Combination] = []
    visited, truncated = 0, False

    def visit(start: int, lines: tuple, count: int):
        nonlocal visited, truncated
        if visited >= c.max_states:
            truncated = True
            return
        visited += 1
        if lines:
            n = Nutrients.total([(i.nutrition, q) for i, q in lines])
            price = sum(i.price_fen * q for i, q in lines) + c.delivery_fee_fen
            # Price may fall after official coupons. Preserve over-budget candidates when quoting.
            check_profile = p.model_copy(update={"budget": 10000}) if allow_over_budget else p
            if feasible(n, price, check_profile, c):
                found.append(Combination(lines, n, price, "menu + delivery fee; 未经官方算价"))
            if (
                (not allow_over_budget and price > fen(p.budget))
                or (c.max_kcal is not None and n.kcal > c.max_kcal)
                or (c.max_fat_g is not None and n.fat_g > c.max_fat_g)
                or (c.max_carbs_g is not None and n.carbs_g > c.max_carbs_g)
            ):
                return
        if count == c.max_items:
            return
        for j in range(start, len(eligible)):
            for q in range(1, min(eligible[j].max_quantity, c.max_items - count) + 1):
                if visited >= c.max_states:
                    truncated = True
                    return
                visit(j + 1, lines + ((eligible[j], q),), count + q)

    visit(0, (), 0)
    return SearchResult(
        found,
        not truncated,
        visited,
        len(items) - len(eligible),
        f"当前合格菜单，至多{c.max_items}份，商品各自限量，最多{c.max_states}搜索节点",
    )


def rank(candidates: list[Combination], p: Profile, t: Targets) -> dict[str, Combination]:
    if not candidates:
        return {}

    def common(x):
        n = x.nutrition
        center = sum(t.meal_kcal) / 2 if t.meal_kcal else None
        deviation = abs(n.kcal - center) / center if center else 0
        protein_gap = max(0, 1 - n.protein_g / t.meal_protein_g[0]) if t.meal_protein_g else 0
        fats = max(0, n.fat_g / t.meal_fat_g - 1) if t.meal_fat_g else 0
        carbs = abs(n.carbs_g / t.meal_carbs_g - 1) if t.meal_carbs_g else 0
        preference = sum(q for i, q in x.lines if set(p.likes) & set(i.tags))
        return deviation, protein_gap, fats, carbs, preference

    def score(x, mode):
        d, gap, fat, carb, pref = common(x)
        n = x.nutrition
        if mode == "protein":
            return (-n.protein_g, d, -pref, x.price_fen, x.key)
        if mode == "value":
            # Normalize price/protein. Zero protein is never a value winner when alternatives exist.
            ratio = x.price_fen / 100 / max(n.protein_g, 0.01)
            return (
                ratio
                + 2 * gap
                + (2 if p.goal == "cut" else 0.5) * d
                + 0.2 * fat
                + 0.1 * carb
                - 0.03 * pref,
                x.price_fen,
                x.key,
            )
        return (
            d + 0.5 * gap + 0.25 * fat + 0.1 * carb - 0.02 * pref,
            -n.protein_g,
            x.price_fen,
            x.key,
        )

    # Objectives can legitimately yield the same meal; do not manufacture distinct options.
    return {
        mode: min(candidates, key=lambda x: score(x, mode))
        for mode in ("protein", "value", "calorie")
    }


def apply_price(
    x: Combination,
    total_fen: int,
    source: str,
    *,
    original_fen=None,
    discount_fen=None,
    delivery_fen=None,
    packing_fen=None,
) -> Combination:
    if total_fen < 0:
        raise ValueError("价格不能为负")
    return replace(
        x,
        price_fen=total_fen,
        price_source=source,
        quoted=True,
        original_fen=original_fen,
        discount_fen=discount_fen,
        delivery_fen=delivery_fen,
        packing_fen=packing_fen,
    )

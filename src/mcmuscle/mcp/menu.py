from datetime import UTC, datetime

from mcmuscle.models import Item, fen
from mcmuscle.nutrition.catalog import match


def menu_items(data: dict, foods, *, details: dict | None = None):
    """Exact matching only. Do not equate menu category/tags with verified ingredients."""
    if not isinstance(data.get("meals"), dict):
        raise ValueError("菜单 schema 已变化")
    active = {m["code"] for c in data.get("categories", []) for m in c.get("meals", [])}
    items, rejected = [], []
    for code, row in sorted(data["meals"].items()):
        food = match(row["name"], foods)
        detail = (details or {}).get(code)
        if (
            code not in active
            or not food
            or row.get("canWithOrder")
            or (detail and detail.get("rounds"))
        ):
            rejected.append(code)
            continue
        # If detail is absent this is provisional and must be verified before quoting/ordering.
        tags = tuple(
            tag
            for word, tag in (("牛", "beef"), ("鸡", "chicken"), ("鱼", "fish"))
            if word in row["name"]
        )
        items.append(
            Item(
                id=code,
                name=row["name"],
                nutrition=food.nutrition,
                price_fen=fen(row["currentPrice"]),
                source=food.source + " + query-meals",
                retrieved_at=datetime.now(UTC).isoformat(),
                tags=tags,
            )
        )
    return items, rejected


def valid_store(store: dict, reservation: str | None = None):
    if reservation:
        if not store.get("reservation"):
            raise ValueError("该门店不支持预约")
        if reservation.split()[0] not in {
            x["date"] for x in store.get("reservationTimeOptions", [])
        }:
            raise ValueError("预约日期不在门店可选范围；时间段还须官方算价验证")
    elif store.get("businessStatus") is not True:
        raise ValueError("该门店当前未营业或状态不明")

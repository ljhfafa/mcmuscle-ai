import re
import unicodedata
from collections.abc import Mapping

from mcmuscle.models import Food, Nutrients, finite

FIELDS = {
    "kcal": ("kcal", "energy_kcal", "热量(kcal)", "能量(kcal)", "热量（千卡）"),
    "protein_g": ("protein_g", "protein", "蛋白质(g)", "蛋白质（克）"),
    "carbs_g": ("carbs_g", "carbohydrate", "碳水化合物(g)", "碳水化合物（克）"),
    "fat_g": ("fat_g", "fat", "脂肪(g)", "脂肪（克）"),
    "sodium_mg": ("sodium_mg", "钠(mg)", "钠（毫克）"),
    "calcium_mg": ("calcium_mg", "钙(mg)", "钙（毫克）"),
}


def normalize(name: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", name).casefold()).replace("®", "")


def quantity(value, unit):
    if value is None or str(value).strip() in ("", "-", "N/A", "未知"):
        return None
    if isinstance(value, bool):
        raise ValueError("布尔值不是营养值")
    if isinstance(value, (float, int)):
        return finite(value)
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(kcal|千卡|kj|kJ|g|克|mg|毫克)?\s*", str(value))
    if not m:
        raise ValueError("未知营养单位或非法值")
    n, actual = finite(m[1]), m[2]
    if (
        actual is None
        or actual in {"kcal": ("kcal", "千卡"), "g": ("g", "克"), "mg": ("mg", "毫克")}[unit]
    ):
        return n
    if unit == "kcal" and actual.lower() == "kj":
        return n / 4.184
    if unit == "mg" and actual in ("g", "克"):
        return n * 1000
    raise ValueError("营养单位不匹配")


def parse_catalog(
    rows: list[dict], *, source: str, retrieved_at: str, field_map: Mapping[str, str] | None = None
) -> tuple[list[Food], list[str]]:
    """field_map is explicit: canonical field -> observed official key with known unit.
    Unlabelled energy/sodium fields deliberately require mapping, never guess units.
    """
    foods, problems = [], []
    seen: dict[str, Food] = {}
    for idx, row in enumerate(rows):
        try:
            name_key = (field_map or {}).get("name")
            name = (
                row.get(name_key)
                if name_key
                else next(
                    (row[k] for k in ("name", "foodName", "餐品名称", "名称") if k in row), None
                )
            )
            if not isinstance(name, str) or not name.strip():
                raise ValueError("缺少餐品名")
            values = {}
            for field, keys in FIELDS.items():
                explicit = (field_map or {}).get(field)
                matches = [k for k in ((explicit,) if explicit else keys) if k in row]
                if len(matches) > 1:
                    raise ValueError("同一营养字段存在歧义")
                raw = row[matches[0]] if matches else None
                values[field] = quantity(
                    raw, "kcal" if field == "kcal" else "mg" if field.endswith("_mg") else "g"
                )
            nutrient = Nutrients(**values)
            food = Food(
                name=name.strip(),
                nutrition=nutrient,
                source=source,
                retrieved_at=retrieved_at,
                updated_at=row.get("updated_at"),
            )
            key = normalize(food.name)
            if key in seen:
                if seen[key].nutrition != food.nutrition:
                    raise ValueError("同名餐品营养冲突；整个名称需排除")
                continue
            seen[key] = food
            foods.append(food)
        except (ValueError, TypeError):
            problems.append(f"row {idx}: 缺失/非法/歧义数据，已隔离")
            if isinstance(row, dict):
                candidate = row.get(
                    (field_map or {}).get("name", "name"),
                    row.get("foodName", row.get("餐品名称", row.get("名称", ""))),
                )
                if isinstance(candidate, str):
                    key = normalize(candidate)
                    foods = [f for f in foods if normalize(f.name) != key]
                    # Keep conflict sentinel to reject any subsequent duplicate.
    return foods, problems


def match(name: str, foods: list[Food], aliases: Mapping[str, str] | None = None) -> Food | None:
    key = normalize(name)
    if aliases:
        key = normalize({normalize(k): v for k, v in aliases.items()}.get(key, name))
    matches = [f for f in foods if key in {normalize(f.name), *(normalize(x) for x in f.aliases)}]
    return matches[0] if len(matches) == 1 else None


def bundle(components: list[tuple[Food, int]]) -> Nutrients:
    if not components or any(type(q) is not int or q <= 0 for _, q in components):
        raise ValueError("套餐必须有完整组件及正整数数量")
    return Nutrients.total([(f.nutrition, q) for f, q in components])

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Profile(Record):
    goal: Literal["gain", "cut", "maintain", "free"] = "free"
    budget: float = Field(gt=0, le=10000)
    weight_kg: float | None = Field(default=None, ge=25, le=350)
    height_cm: float | None = Field(default=None, ge=100, le=250)
    age: int | None = Field(default=None, ge=1, le=110)
    sex: Literal["male", "female"] | None = None
    activity: Literal["sedentary", "light", "moderate", "active"] | None = None
    training_days: int | None = Field(default=None, ge=0, le=7)
    special_population: bool = False
    meal_fraction: float = Field(default=1 / 3, ge=0.15, le=0.5)
    meal_kcal: float | None = Field(default=None, ge=300, le=1800)
    likes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    allergies: tuple[str, ...] = ()
    meal: str | None = None
    priority: Literal["balanced", "protein", "value"] = "balanced"


class Nutrients(Record):
    kcal: float = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbs_g: float = Field(ge=0, le=2000)
    fat_g: float = Field(ge=0, le=1000)
    sodium_mg: float | None = Field(default=None, ge=0, le=100000)
    calcium_mg: float | None = Field(default=None, ge=0, le=100000)

    @classmethod
    def total(cls, values: list[tuple[Nutrients, int]]) -> Nutrients:
        result = {}
        for field in cls.model_fields:
            result[field] = (
                None
                if any(getattr(n, field) is None for n, _ in values)
                else sum(getattr(n, field) * q for n, q in values)
            )
        return cls.model_validate(result)


class Food(Record):
    name: str = Field(min_length=1)
    nutrition: Nutrients
    source: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    updated_at: str | None = None
    aliases: tuple[str, ...] = ()


class Item(Record):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    nutrition: Nutrients
    price_fen: int = Field(ge=0)
    source: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    allergens: tuple[str, ...] = ()
    allergens_verified: bool = False
    ingredients_verified: bool = False
    available: bool = True
    max_quantity: int = Field(default=2, ge=1, le=4)
    # One atomic purchasable selection. A bundle is summed once, never with its components again.
    components: tuple[str, ...] = ()
    customized: bool = False


class Targets(Record):
    bmr: float | None = None
    tdee: float | None = None
    daily_kcal: float | None = None
    daily_protein_g: tuple[float, float] | None = None
    daily_carbs_g: float | None = None
    daily_fat_g: float | None = None
    meal_kcal: tuple[float, float] | None = None
    meal_protein_g: tuple[float, float] | None = None
    meal_carbs_g: float | None = None
    meal_fat_g: float | None = None
    notes: tuple[str, ...] = ()


class Constraints(Record):
    max_items: int = Field(default=4, ge=1, le=8)
    max_states: int = Field(default=80000, ge=1, le=1000000)
    min_kcal: float = Field(default=0, ge=0)
    max_kcal: float | None = Field(default=None, gt=0)
    min_protein_g: float = Field(default=0, ge=0)
    max_fat_g: float | None = Field(default=None, gt=0)
    max_carbs_g: float | None = Field(default=None, gt=0)
    delivery_fee_fen: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_range(self):
        if self.max_kcal is not None and self.min_kcal > self.max_kcal:
            raise ValueError("热量下限不能大于上限")
        return self


def fen(yuan: object) -> int:
    from decimal import Decimal

    value = Decimal(str(yuan))
    if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError("金额必须为非负、最多两位小数的人民币元")
    return int(value * 100)


def finite(value: object) -> float:
    x = float(value)  # type: ignore[arg-type]
    if not math.isfinite(x) or x < 0:
        raise ValueError("营养值必须是有限非负数")
    return x

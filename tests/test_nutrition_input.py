import pytest
from pydantic import ValidationError

from mcmuscle.input import parse
from mcmuscle.models import Profile, fen
from mcmuscle.nutrition.engine import NutritionConfig, targets


def full(**overrides):
    return Profile.model_validate(
        dict(
            budget=40,
            weight_kg=75,
            height_cm=180,
            age=25,
            sex="male",
            activity="moderate",
            **overrides,
        )
    )


def test_natural_language():
    p = parse(
        "我男，25岁，180cm，75kg，每周力量训练4次，现在增肌，今天午餐预算40元，喜欢牛肉，不喜欢鱼，尽量让我摄入更多蛋白质"
    )
    assert (p.age, p.sex, p.height_cm, p.weight_kg, p.training_days, p.goal, p.budget) == (
        25,
        "male",
        180,
        75,
        4,
        "gain",
        40,
    )
    assert p.likes == ("beef",) and p.excludes == ("fish",) and p.meal == "lunch"
    assert p.activity is None and p.priority == "protein"


def test_english():
    p = parse(
        "female, 28 years old, 60kg, 165cm, cut, budget 35 yuan, prefer chicken, allergic to peanut"
    )
    assert p.sex == "female" and p.allergies == ("peanut",) and p.likes == ("chicken",)


@pytest.mark.parametrize(
    "field,value",
    [
        ("height_cm", 10),
        ("weight_kg", -1),
        ("weight_kg", float("nan")),
        ("training_days", 8),
        ("budget", 0),
        ("age", 150),
    ],
)
def test_invalid_input(field, value):
    with pytest.raises(ValidationError):
        Profile.model_validate({"budget": 40, field: value})


@pytest.mark.parametrize(
    "goal,multiplier", [("gain", 1.10), ("cut", 0.85), ("maintain", 1), ("free", 1)]
)
def test_targets(goal, multiplier):
    t = targets(full(goal=goal))
    assert t.bmr == 1755
    assert t.tdee == pytest.approx(2720.25)
    assert t.daily_kcal == pytest.approx(2720.25 * multiplier)
    assert t.daily_protein_g == (105, 150)
    assert t.meal_protein_g == (35, 50)
    assert t.daily_fat_g * 9 + t.daily_carbs_g * 4 + 127.5 * 4 == pytest.approx(t.daily_kcal)
    assert sum(t.meal_kcal) / 2 == pytest.approx(t.daily_kcal / 3)


def test_incomplete_never_fakes_tdee():
    t = targets(parse("75kg，增肌，预算40"))
    assert t.tdee is None and t.bmr is None and t.meal_protein_g == (35, 50)
    assert t.meal_kcal is None


@pytest.mark.parametrize("kwargs", [{"age": 17}, {"special_population": True}, {"age": 80}])
def test_special_population(kwargs):
    assert targets(Profile(budget=40, weight_kg=60, **kwargs)).daily_protein_g is None


def test_underweight_cut():
    assert targets(Profile(budget=40, weight_kg=45, height_cm=180, goal="cut")).daily_kcal is None


def test_aggressive_config():
    with pytest.raises(ValueError):
        NutritionConfig(deficit=0.8)


def test_no_invented_input():
    p = parse("预算30，减脂")
    assert p.age is None and p.weight_kg is None and p.sex is None
    with pytest.raises(ValueError):
        parse("帮我吃午饭")
    with pytest.raises(ValueError):
        parse("预算30，增肌减脂")


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), -1, "1.005"])
def test_money_invalid(amount):
    with pytest.raises(ValueError):
        fen(amount)


def test_fen_exact():
    assert fen("33.50") == 3350

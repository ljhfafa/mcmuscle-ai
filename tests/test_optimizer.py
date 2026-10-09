from itertools import product

import pytest

from mcmuscle.demo import menu
from mcmuscle.models import Constraints, Profile, Targets
from mcmuscle.nutrition.engine import targets
from mcmuscle.optimizer.engine import rank, search


def test_global_small_space_against_independent_brute_force():
    items = menu()[:3]
    p = Profile(budget=40)
    c = Constraints(max_items=3)
    result = search(items, p, c)
    expected = set()
    for quantities in product(range(3), repeat=3):
        if (
            0 < sum(quantities) <= 3
            and sum(i.price_fen * q for i, q in zip(items, quantities, strict=True)) <= 4000
        ):
            expected.add(
                tuple(sorted((i.id, q) for i, q in zip(items, quantities, strict=True) if q))
            )
    assert {x.key for x in result.candidates} == expected
    assert result.exhaustive
    best = rank(result.candidates, p, Targets())["protein"]
    assert best.nutrition.protein_g == max(x.nutrition.protein_g for x in result.candidates)


def test_budget_and_delivery():
    p = Profile(budget=20)
    assert all(
        x.price_fen <= 2000 for x in search(menu(), p, Constraints(delivery_fee_fen=600)).candidates
    )
    assert not search(menu(), Profile(budget=1)).candidates


def test_hard_nutrients():
    c = Constraints(max_kcal=600, min_kcal=200, min_protein_g=20, max_fat_g=30, max_carbs_g=80)
    result = search(menu(), Profile(budget=40), c)
    assert result.candidates
    assert all(
        200 <= x.nutrition.kcal <= 600 and x.nutrition.protein_g >= 20 and x.nutrition.fat_g <= 30
        for x in result.candidates
    )


def test_exclusion_and_allergy():
    p = Profile(budget=40, excludes=("fish",), allergies=("milk",))
    result = search(menu(), p)
    assert result.candidates
    assert all(not ({"fish", "milk"} & set(i.tags)) for x in result.candidates for i, _ in x.lines)
    unknown = [i.model_copy(update={"allergens_verified": False}) for i in menu()]
    assert not search(unknown, p).candidates


def test_unknown_ingredients_excluded():
    items = [i.model_copy(update={"ingredients_verified": False}) for i in menu()]
    assert not search(items, Profile(budget=40, excludes=("fish",))).candidates


def test_preference_tiebreak():
    a, b = menu()[:2]
    b = b.model_copy(update={"nutrition": a.nutrition, "price_fen": a.price_fen})
    p = Profile(budget=18, likes=("beef",))
    assert rank(search([a, b], p).candidates, p, Targets())["protein"].lines[0][0].id == a.id


def test_metrics_zero_and_exact():
    p = Profile(budget=18, weight_kg=75)
    x = rank(search(menu()[:1], p).candidates, p, targets(p))["protein"]
    m = x.metrics(targets(p))
    assert m["yuan_per_protein_g"] == pytest.approx(18 / 26)
    assert m["protein_per_100_kcal"] == pytest.approx(26 / 420 * 100)
    assert m["protein_target_ratio"] == pytest.approx(26 / 35)


def test_bounded_deterministic():
    p = Profile(budget=100)
    c = Constraints(max_states=5)
    a, b = search(menu(), p, c), search(list(reversed(menu())), p, c)
    assert a.visited <= 5 and not a.exhaustive and a.candidates == b.candidates


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        search([menu()[0], menu()[0]], Profile(budget=40))


def test_unavailable_customization():
    assert not search(
        [menu()[0].model_copy(update={"available": False})], Profile(budget=40)
    ).candidates
    assert not search(
        [menu()[0].model_copy(update={"customized": True})], Profile(budget=40)
    ).candidates


def test_discount_candidates_survive_pre_filter():
    p = Profile(budget=10)
    assert not search(menu()[:1], p).candidates
    assert search(menu()[:1], p, allow_over_budget=True).candidates

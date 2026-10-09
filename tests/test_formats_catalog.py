from types import SimpleNamespace

import pytest

from mcmuscle.mcp.formats import FormatError, api_data, decode, toon, unwrap
from mcmuscle.mcp.official import NUTRITION_FIELDS
from mcmuscle.nutrition.catalog import bundle, match, parse_catalog, quantity

SYNTHETIC_TOON = "[2]{productName,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n  MOCK A,400,20,15,40,500,100\n  MOCK B,120,8,5,10,60,200"


def foods():
    return parse_catalog(
        toon(SYNTHETIC_TOON),
        source="MOCK DEMO",
        retrieved_at="synthetic",
        field_map=NUTRITION_FIELDS,
    )[0]


def test_toon_catalog():
    fs = foods()
    assert len(fs) == 2 and fs[0].nutrition.sodium_mg == 500


def test_json_envelope():
    result = SimpleNamespace(
        isError=False, structuredContent={"success": True, "code": 200, "data": SYNTHETIC_TOON}
    )
    assert len(api_data(result)) == 2


def test_text_envelope():
    import json

    text = "# API Response Information\n## Original Response\n" + json.dumps(
        {"success": True, "data": SYNTHETIC_TOON}
    )
    result = SimpleNamespace(
        isError=False, structuredContent=None, content=[SimpleNamespace(type="text", text=text)]
    )
    assert len(api_data(result)) == 2


def test_nested_and_quoted_delimiters():
    import json

    text = "data:\n  foods[1]{name,protein}:\n    " + json.dumps('MOCK, "A"') + ",12"
    assert toon(text)["data"]["foods"][0]["name"] == 'MOCK, "A"'
    assert toon("foods[1|]{name|protein}:\n  A|12")["foods"][0]["protein"] == 12


@pytest.mark.parametrize(
    "s",
    [
        "x[2]{a,b}:\n  1,2",
        "x[1]{a,b}:\n  1,2,3",
        "x[1]{a,a}:\n  1,2",
        "x: 1\nx: 2",
        'x[1]{a,b}:\n  "abc,2',
        "- foo: 2",
    ],
)
def test_bad_toon(s):
    with pytest.raises(FormatError):
        toon(s)


def test_bad_tool_result():
    with pytest.raises(FormatError):
        unwrap(SimpleNamespace(isError=True))
    with pytest.raises(FormatError):
        unwrap(SimpleNamespace(isError=False, structuredContent=None, content=[]))
    with pytest.raises(FormatError):
        api_data(SimpleNamespace(isError=False, structuredContent={"success": False}))


def test_alias_no_fuzzy_match():
    fs = foods()
    assert match("ＭＯＣＫ A", fs) == fs[0]
    assert match("test", fs, {"test": "MOCK A"}) == fs[0]
    assert match("MOCK", fs) is None


def test_missing_nutrition_quarantined():
    fs, issues = parse_catalog([{"name": "MOCK", "kcal": 400}], source="MOCK", retrieved_at="test")
    assert not fs and len(issues) == 1


def test_duplicates_and_conflict():
    rows = toon(SYNTHETIC_TOON)
    assert (
        len(
            parse_catalog(
                [rows[0], rows[0]], source="MOCK", retrieved_at="test", field_map=NUTRITION_FIELDS
            )[0]
        )
        == 1
    )
    bad = {**rows[0], "protein": 200}
    assert not parse_catalog(
        [rows[0], bad, rows[0]], source="MOCK", retrieved_at="test", field_map=NUTRITION_FIELDS
    )[0]


def test_units_and_bundle():
    assert quantity("418.4 kJ", "kcal") == pytest.approx(100)
    assert quantity("0.5 g", "mg") == 500


def test_bundle_totals():
    fs = foods()
    total = bundle([(fs[0], 2), (fs[1], 1)])
    assert total.kcal == 920 and total.protein_g == 48 and total.calcium_mg == 400
    with pytest.raises(ValueError):
        bundle([(fs[0], 0)])


@pytest.mark.parametrize(
    "x,u", [("5 oz", "g"), ("nan", "g"), ("-1", "g"), ("10 mg", "g"), (True, "g")]
)
def test_bad_units(x, u):
    with pytest.raises(ValueError):
        quantity(x, u)


def test_json():
    assert decode('```json\n{"a":1}\n```') == {"a": 1}

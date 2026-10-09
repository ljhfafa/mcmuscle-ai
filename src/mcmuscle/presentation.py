import html

from mcmuscle.models import Profile, Targets

LABELS = {"protein": "A · 蛋白质大王", "value": "B · 省钱肌肉王", "calorie": "C · 热量控制王"}


def render(results, p: Profile, t: Targets, *, mock: bool, scope: str) -> str:
    def cell(s):
        return html.escape(str(s)).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# 💪 麦麦肌肉大王 · McMuscle AI",
        "",
        "**MOCK DEMO — 以下餐品、营养和价格全部为合成测试数据。**"
        if mock
        else "**实时来源数据；最终价格与供应状态以本次官方算价为准。**",
        "",
        f"目标：{p.goal} · 预算：¥{p.budget:.2f}",
        "",
        *t.notes,
        "",
        scope,
        "",
    ]
    if not results:
        lines.append(
            "没有找到满足全部硬约束的方案。搜索若被截断，不代表全空间无解；可询问用户是否调整条件。"
        )
        return "\n".join(lines)
    lines.extend(
        [
            "|方案|餐品|kcal|蛋白质 g|碳水 g|脂肪 g|含已知配送费 ¥|¥/蛋白质 g|蛋白质/100 kcal|蛋白质/100元|热量偏差|蛋白目标达成|",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    def fmt(x):
        return "未设/不可算" if x is None else f"{x:.2f}"

    for mode, x in results.items():
        n, m = x.nutrition, x.metrics(t)
        names = " + ".join(f"{cell(i.name)}×{q}" for i, q in x.lines)
        lines.append(
            f"|{LABELS[mode]}|{names}|{n.kcal:.0f}|{n.protein_g:.1f}|{n.carbs_g:.1f}|{n.fat_g:.1f}|{x.price_fen / 100:.2f}|{fmt(m['yuan_per_protein_g'])}|{fmt(m['protein_per_100_kcal'])}|{fmt(m['protein_per_100_yuan'])}|{fmt(m['kcal_deviation'])}|{fmt(m['protein_target_ratio'])}|"
        )
    for mode, x in results.items():
        rationale = {
            "protein": "在搜索候选及硬约束内优先提高蛋白质",
            "value": "综合每克蛋白质成本、目标缺口、热量偏差与偏好",
            "calorie": "综合热量偏差、蛋白质缺口及脂肪/碳水目标",
        }[mode]
        lines.extend(
            [
                "",
                f"**{LABELS[mode]}**：{rationale}。价格来源：{cell(x.price_source)}。",
                "营养来源："
                + "；".join(
                    sorted({cell(i.source) + " / 获取 " + cell(i.retrieved_at) for i, _ in x.lines})
                ),
            ]
        )
        n = x.nutrition
        lines.append(
            f"钠：{fmt(n.sodium_mg)} mg；钙：{fmt(n.calcium_mg)} mg。官方营养更新时间：未提供。"
        )
        if x.quoted:
            lines.append(
                f"订单原价 ¥{fmt(x.original_fen / 100 if x.original_fen is not None else None)}；优惠 ¥{fmt(x.discount_fen / 100 if x.discount_fen is not None else None)}；配送费 ¥{fmt(x.delivery_fen / 100 if x.delivery_fen is not None else None)}；应付 ¥{x.price_fen / 100:.2f}。性价比含该配送费及打包费。"
            )
    if p.goal == "cut" and t.meal_kcal is None:
        lines.append("\n尚未提供足够信息或本餐热量目标，不能判断方案符合减脂热量控制。")
    if len({x.key for x in results.values()}) < len(results):
        lines.append("\n部分目标得到相同组合，已如实保留，未人为制造不同方案。")
    lines.append(
        "\n可调整预算/目标、更换门店或选择方案。下单前须重新算价，展示完整明细并明确确认。"
    )
    return "\n".join(lines)

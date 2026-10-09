from dataclasses import dataclass

from mcmuscle.models import Profile, Targets


@dataclass(frozen=True)
class NutritionConfig:
    deficit: float = 0.15
    surplus: float = 0.10
    protein_low: float = 1.4
    protein_high: float = 2.0
    fat_fraction: float = 0.30

    def __post_init__(self):
        if not 0 <= self.deficit <= 0.20 or not 0 <= self.surplus <= 0.15:
            raise ValueError("拒绝激进热量缺口/盈余")
        if not 1.0 <= self.protein_low <= self.protein_high <= 2.0:
            raise ValueError("成人一般运动蛋白质配置超出支持范围")
        if not 0.20 <= self.fat_fraction <= 0.35:
            raise ValueError("脂肪比例超出支持范围")


def targets(p: Profile, config: NutritionConfig | None = None) -> Targets:
    config = config or NutritionConfig()
    if p.special_population or (p.age is not None and not 18 <= p.age <= 78):
        return Targets(
            notes=("特殊人群或年龄超出适用范围：不使用普通成人健身公式；可比较官方餐品数据。",)
        )
    if (
        p.weight_kg
        and p.height_cm
        and p.weight_kg / (p.height_cm / 100) ** 2 < 18.5
        and p.goal == "cut"
    ):
        return Targets(notes=("体重偏低，不生成减脂热量目标；可比较餐品信息并寻求专业评估。",))
    notes = ["公式仅为健康成人的起始估算，不是精确测量；日常饮食应多样化。"]
    if p.age is None:
        notes.append("年龄未知：以下范围仅适用于已成年且非特殊健康状况的人群。")
    protein = (
        (p.weight_kg * config.protein_low, p.weight_kg * config.protein_high)
        if p.weight_kg
        else None
    )
    bmr = tdee = daily = carbs = fat = None
    kcal = None
    if all(v is not None for v in (p.weight_kg, p.height_cm, p.age, p.sex, p.activity)):
        assert p.weight_kg and p.height_cm and p.age and p.activity
        bmr = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age + (5 if p.sex == "male" else -161)
        factor = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}[p.activity]
        tdee = bmr * factor
        daily = (
            tdee
            * {"gain": 1 + config.surplus, "cut": 1 - config.deficit, "maintain": 1.0, "free": 1.0}[
                p.goal
            ]
        )
        # Conservative product guardrail, not a clinical lower-calorie threshold.
        daily = max(daily, bmr)
        fat = daily * config.fat_fraction / 9
        assert protein
        carbs = max(0, (daily - fat * 9 - sum(protein) / 2 * 4) / 4)
        center = daily * p.meal_fraction
        kcal = (center * 0.9, center * 1.1)
        notes.append("活动系数是可调整的规划假设；每周训练次数本身不足以确定全天活动水平。")
    else:
        notes.append("缺少完整身体/活动参数：不计算 BMR/TDEE；可按蛋白质范围与预算比较。")
    if p.meal_kcal is not None:
        kcal = (p.meal_kcal * 0.9, p.meal_kcal * 1.1)
        notes.append("本餐热量使用用户明确设置的规划目标。")
    return Targets(
        bmr=bmr,
        tdee=tdee,
        daily_kcal=daily,
        daily_protein_g=protein,
        daily_carbs_g=carbs,
        daily_fat_g=fat,
        meal_kcal=kcal,
        meal_protein_g=(protein[0] * p.meal_fraction, protein[1] * p.meal_fraction)
        if protein
        else None,
        meal_carbs_g=carbs * p.meal_fraction if carbs is not None else None,
        meal_fat_g=fat * p.meal_fraction if fat is not None else None,
        notes=tuple(notes),
    )

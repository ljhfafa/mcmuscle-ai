"""Conservative convenience parser. Codex supplies a validated Profile for unrestricted language."""

import re

from mcmuscle.models import Profile

FOODS = {
    "牛肉": "beef",
    "beef": "beef",
    "鱼": "fish",
    "fish": "fish",
    "鸡肉": "chicken",
    "chicken": "chicken",
    "花生": "peanut",
    "peanut": "peanut",
    "牛奶": "milk",
    "milk": "milk",
    "鸡蛋": "egg",
    "egg": "egg",
    "大豆": "soy",
    "小麦": "wheat",
    "虾": "shellfish",
}


def parse(text: str) -> Profile:
    s = text.lower()

    def num(pattern):
        m = re.search(pattern, s)
        return float(m.group(1)) if m else None

    data = {"budget": num(r"(?:预算|budget[^0-9]*|¥|￥)(\d+(?:\.\d+)?)")}
    if data["budget"] is None:
        raise ValueError("请提供本餐预算，例如预算40元 / budget 40 yuan")
    data.update(
        weight_kg=num(r"(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)"),
        height_cm=num(r"(\d+(?:\.\d+)?)\s*(?:cm|厘米)"),
        age=num(r"(\d+)\s*(?:岁|years? old|y/o)"),
        training_days=num(r"(?:每周[^，。,.]*?|train\s*)([0-7])\s*(?:次|days)"),
    )
    if re.search(r"女|\bfemale\b|\bwoman\b", s):
        data["sex"] = "female"
    elif re.search(r"男|\bmale\b|\bman\b", s):
        data["sex"] = "male"
    goals = [
        g
        for g, pattern in [
            ("gain", r"增肌|bulk|gain muscle"),
            ("cut", r"减脂|减肥|cut|lose fat"),
            ("maintain", r"维持|maintain"),
        ]
        if re.search(pattern, s)
    ]
    if len(goals) > 1:
        raise ValueError("检测到多个目标，请明确本次目标")
    data["goal"] = goals[0] if goals else "free"
    likes, excludes, allergies = set(), set(), set()
    for clause in re.split(r"[，。,.;；]|\band\b|\bbut\b", s):
        for word, tag in FOODS.items():
            if word not in clause:
                continue
            if re.search(r"过敏|allerg", clause):
                allergies.add(tag)
            elif re.search(r"不喜欢|不吃|不要|讨厌|avoid|dislike|don't like|no ", clause):
                excludes.add(tag)
            elif re.search(r"喜欢|like|prefer|love", clause):
                likes.add(tag)
    data.update(
        likes=tuple(sorted(likes - excludes - allergies)),
        excludes=tuple(sorted(excludes)),
        allergies=tuple(sorted(allergies)),
        special_population=bool(
            re.search(r"孕|哺乳|肾病|严重疾病|pregnan|breastfeed|kidney disease", s)
        ),
    )
    if re.search(r"高蛋白|更多蛋白|high protein", s):
        data["priority"] = "protein"
    for word, meal in [
        ("午餐", "lunch"),
        ("晚餐", "dinner"),
        ("早餐", "breakfast"),
        ("lunch", "lunch"),
        ("dinner", "dinner"),
        ("breakfast", "breakfast"),
    ]:
        if word in s:
            data["meal"] = meal
    return Profile.model_validate(data)

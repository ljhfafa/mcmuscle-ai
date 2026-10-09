"""Entirely synthetic data, never passed to live ordering."""

from mcmuscle.models import Item, Nutrients


def menu():
    rows = [
        ("mock-beef", "MOCK 牛肉堡", 1800, 420, 26, 38, 18, ("beef", "wheat", "milk")),
        ("mock-chicken", "MOCK 鸡肉堡", 1500, 390, 24, 40, 15, ("chicken", "wheat", "egg")),
        ("mock-fish", "MOCK 鱼肉堡", 1600, 370, 18, 39, 16, ("fish", "wheat", "milk")),
        ("mock-milk", "MOCK 牛奶", 800, 130, 8, 12, 6, ("milk",)),
        ("mock-side", "MOCK 小配餐", 600, 170, 3, 22, 8, ("wheat",)),
    ]
    return [
        Item(
            id=i,
            name=name,
            nutrition=Nutrients(
                kcal=k, protein_g=p, carbs_g=c, fat_g=f, sodium_mg=300, calcium_mg=80
            ),
            price_fen=price,
            source="MOCK DEMO 合成数据",
            retrieved_at="synthetic",
            tags=tags,
            allergens=tags,
            allergens_verified=True,
            ingredients_verified=True,
        )
        for i, name, price, k, p, c, f, tags in rows
    ]

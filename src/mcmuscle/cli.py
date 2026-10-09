import argparse
import asyncio
import json
from pathlib import Path

from mcmuscle.input import parse
from mcmuscle.models import Constraints, Item, Profile
from mcmuscle.nutrition.engine import targets
from mcmuscle.optimizer.engine import rank, search
from mcmuscle.presentation import render


def main():
    parser = argparse.ArgumentParser(description="McMuscle AI / 麦麦肌肉大王")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="无网络无 Token 的合成演示")
    demo.add_argument("--text", default="我75kg，正在增肌，预算40块，喜欢牛肉，不喜欢鱼")
    demo.add_argument("--profile", type=Path)
    recommend = sub.add_parser("recommend", help="校验并计算官方数据规范化后的输入")
    recommend.add_argument("input", type=Path)
    sub.add_parser("setup-token", help="macOS 隐藏输入并保存新 Token 到钥匙串")
    live = sub.add_parser("probe", help="仅发现工具和读取营养数据")
    live.add_argument("--save-private", type=Path)
    live_meal = sub.add_parser("live", help="选择门店后的真实只读推荐，不下单")
    live_meal.add_argument("--profile", type=Path, required=True)
    live_meal.add_argument("--city", required=True)
    live_meal.add_argument("--keyword", required=True)
    live_meal.add_argument("--store-code", required=True)
    live_meal.add_argument("--quote-limit", type=int, default=6)
    args = parser.parse_args()
    try:
        if args.command == "live":
            asyncio.run(live_recommend(args))
            return
        if args.command == "setup-token":
            from mcmuscle.mcp.credentials import setup

            setup()
            return
        if args.command == "probe":
            asyncio.run(probe(args.save_private))
            return
        if args.command == "demo":
            from mcmuscle.demo import menu

            p = (
                Profile.model_validate_json(args.profile.read_text())
                if args.profile
                else parse(args.text)
            )
            items, c, mock = menu(), Constraints(), True
        else:
            data = json.loads(args.input.read_text())
            p = Profile.model_validate(data["profile"])
            items = [Item.model_validate(i) for i in data["items"]]
            c = Constraints.model_validate(data.get("constraints", {}))
            mock = data.get("mock", True)
            if not mock and any(
                "mock" in i.source.lower() or "mock" in i.id.lower() for i in items
            ):
                raise ValueError("不能将 Mock 餐品标记为真实数据")
        t = targets(p)
        if p.goal == "cut" and t.meal_kcal and c.max_kcal is None:
            c = c.model_copy(update={"max_kcal": t.meal_kcal[1]})
        result = search(items, p, c)
        scope = (
            result.scope
            + f"；遍历 {result.visited} 节点；"
            + ("该限定空间枚举完成" if result.exhaustive else "已到计算上限，不保证全局最优")
        )
        print(render(rank(result.candidates, p, t), p, t, mock=mock, scope=scope))
    except Exception as e:
        # Validation details can contain personal input; keep CLI failures concise.
        print(f"未完成：{type(e).__name__}。请核对输入、完整字段及安全配置；未输出私人原始数据。")
        raise SystemExit(1) from None


async def probe(destination):
    from mcmuscle.mcp.client import connect
    from mcmuscle.mcp.formats import unwrap

    async with connect() as c:
        result = await c.read("list-nutrition-foods", {})
        data = unwrap(result)
        if destination:
            destination.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.chmod(0o700)
            (destination / "schemas.json").write_text(
                json.dumps(c.schemas, ensure_ascii=False, indent=2)
            )
            (destination / "nutrition.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2)
            )
            for f in destination.iterdir():
                if f.is_file():
                    f.chmod(0o600)
        print(
            json.dumps(
                {
                    "authenticated": True,
                    "tool_count": len(c.schemas),
                    "nutrition_returned": bool(data),
                    "mutations": 0,
                },
                ensure_ascii=False,
            )
        )


async def live_recommend(args):
    from mcmuscle.mcp.client import connect
    from mcmuscle.mcp.official import Official
    from mcmuscle.mcp.workflow import recommend_live

    p = Profile.model_validate_json(args.profile.read_text())
    async with connect() as g:
        api = Official(g)
        stores = await api.nearby(args.city, args.keyword)
        selected = next((s for s in stores if s["storeCode"] == args.store_code), None)
        if selected is None:
            raise ValueError("指定门店不在本次官方返回列表")
        results, t, stats, _ = await recommend_live(
            g, p, selected, api.context(args.store_code), quote_limit=args.quote_limit
        )
        print(render(results, p, t, mock=False, scope=json.dumps(stats, ensure_ascii=False)))


if __name__ == "__main__":
    main()

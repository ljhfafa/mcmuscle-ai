"""Adapters based on tools/list observed on 2026-10-09; validate schema on every call."""

from datetime import UTC, datetime

from mcmuscle.mcp.formats import api_data
from mcmuscle.nutrition.catalog import parse_catalog

NUTRITION_FIELDS = {
    "name": "productName",
    "kcal": "energyKcal",
    "protein_g": "protein",
    "carbs_g": "carbohydrate",
    "fat_g": "fat",
    "sodium_mg": "sodium",
    "calcium_mg": "calcium",
}


class Official:
    def __init__(self, gateway):
        self.gateway = gateway

    async def nutrition(self):
        result = await self.gateway.read("list-nutrition-foods", {})
        rows = api_data(result)
        if not isinstance(rows, list):
            raise ValueError("营养响应 schema 已变化")
        return parse_catalog(
            rows,
            source="https://mcp.mcd.cn / list-nutrition-foods",
            retrieved_at=datetime.now(UTC).isoformat(),
            field_map=NUTRITION_FIELDS,
        )

    async def nearby(self, city: str, keyword: str):
        return api_data(
            await self.gateway.read(
                "query-nearby-stores",
                {"beType": 1, "searchType": 2, "city": city, "keyword": keyword},
            )
        )

    async def addresses(self):
        return api_data(await self.gateway.read("delivery-query-addresses", {}))

    async def delivery_stores(self, address_id: str):
        return api_data(
            await self.gateway.read("delivery-query-stores", {"beType": 2, "addressId": address_id})
        )

    @staticmethod
    def context(store_code: str, *, delivery=False, be_code=None, reservation=None):
        if not store_code or (delivery and not be_code):
            raise ValueError("门店编码/外送业务编码缺失")
        result = {
            "storeCode": store_code,
            "beType": 2 if delivery else 1,
            "orderType": 2 if delivery else 1,
        }
        if delivery:
            result["beCode"] = be_code
        if reservation:
            # China API reservation timestamps carry local wall time, no implicit UTC conversion.
            datetime.strptime(reservation, "%Y-%m-%d %H:%M")
            result["reservationDate"] = reservation
        return result

    async def menu(self, context):
        return api_data(await self.gateway.read("query-meals", context))

    async def detail(self, context, code):
        return api_data(await self.gateway.read("query-meal-detail", {**context, "code": code}))

    async def coupons(self, context):
        out = {}
        for name in ("available-coupons", "query-my-coupons", "query-store-coupons"):
            out[name] = api_data(
                await self.gateway.read(name, context if name == "query-store-coupons" else {})
            )
        return out

    async def quote(self, context, items, *, tableware=False):
        if not items or any(type(i.get("quantity")) is not int or i["quantity"] < 1 for i in items):
            raise ValueError("无效餐品数量")
        return api_data(
            await self.gateway.read(
                "calculate-price",
                {**context, "items": items, "needTableware": tableware},
                fresh=True,
            )
        )

    async def order_status(self, order_id):
        return api_data(await self.gateway.read("query-order", {"orderId": order_id}, fresh=True))

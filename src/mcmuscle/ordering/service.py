"""Confirmation binds a fresh quote and ALL order arguments; durable consume-before-send."""

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from mcmuscle.models import Record


class OrderPlan(Record):
    store: str = Field(min_length=1)
    method: Literal["pickup", "delivery"]
    address: str | None = None
    items: tuple[tuple[str, int], ...]
    coupons: tuple[str, ...] = ()
    total_fen: int = Field(ge=0)
    quoted_at: float
    quote_evidence: str = Field(min_length=1)
    # Canonical JSON string prevents mutation after confirmation.
    arguments_json: str
    mode: Literal["live", "mock"] = "mock"

    def digest(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def summary(self):
        return {
            "门店": self.store,
            "取餐方式": self.method,
            "地址": self.address,
            "餐品与数量": self.items,
            "优惠券": self.coupons,
            "最终应付元": self.total_fen / 100,
            "确认码": self.digest()[:12],
            "状态": "待确认；不会自动付款",
        }


class OrderService:
    def __init__(self, gateway, journal: Path, *, test_mode=True, clock=time.time):
        if test_mode and gateway.live:
            raise ValueError("测试模式禁止真实 MCP 客户端")
        self.gateway, self.test_mode, self.clock = gateway, test_mode, clock
        journal.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(journal, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        self.db = sqlite3.connect(journal)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS attempts (digest TEXT PRIMARY KEY, state TEXT NOT NULL)"
        )
        self.db.commit()

    async def create(self, plan: OrderPlan, confirmation: str):
        if plan.mode != ("live" if self.gateway.live else "mock"):
            raise ValueError("Mock 与真实订单隔离")
        if confirmation != "确认下单 " + plan.digest()[:12]:
            raise ValueError("必须展示最终明细后取得绑定该订单的明确确认")
        if not 0 <= self.clock() - plan.quoted_at <= 120:
            raise ValueError("报价过期或时间异常，须重新算价并确认")
        if not plan.items or any(q <= 0 for _, q in plan.items):
            raise ValueError("餐品/数量无效")
        if plan.method == "delivery" and not plan.address:
            raise ValueError("外送必须确认地址")
        arguments = json.loads(plan.arguments_json)
        allowed = {
            "storeCode",
            "beType",
            "orderType",
            "beCode",
            "reservationDate",
            "items",
            "needTableware",
            "takeWayCode",
            "addressId",
        }
        if set(arguments) - allowed or arguments.get("storeCode") != plan.store:
            raise ValueError("订单参数超范围或门店不一致")
        method = "delivery" if arguments.get("orderType") == 2 else "pickup"
        if method != plan.method or arguments.get("beType") != (2 if method == "delivery" else 1):
            raise ValueError("就餐方式不一致")
        if sorted((i["productCode"], i["quantity"]) for i in arguments.get("items", [])) != sorted(
            plan.items
        ):
            raise ValueError("餐品数量与确认不一致")
        if (
            tuple(sorted(str(i["couponId"]) for i in arguments["items"] if i.get("couponId")))
            != plan.coupons
        ):
            raise ValueError("优惠券与确认不一致")
        if method == "pickup" and not arguments.get("takeWayCode"):
            raise ValueError("缺少确认的堂食/外带方式")
        if method == "delivery" and not arguments.get("addressId"):
            raise ValueError("缺少地址编码")

        try:
            self.db.execute("INSERT INTO attempts VALUES (?, 'sent-or-unknown')", (plan.digest(),))
            self.db.commit()
        except sqlite3.IntegrityError:
            raise ValueError("该确认已使用；先查询订单状态，不能重复创建") from None
        # Once attempted, even failures consume authorization. No auto-retry.
        result = await self.gateway._create_order(arguments)
        self.db.execute("UPDATE attempts SET state='returned' WHERE digest=?", (plan.digest(),))
        self.db.commit()
        return result

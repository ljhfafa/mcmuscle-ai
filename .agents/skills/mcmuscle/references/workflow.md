# 实时调用参考

环境：Python 3.11+，`pip install -e '.[live]'`。离线 demo 不需要网络或凭证。

- `mcmuscle.mcp.client.connect()` 使用官方 Python MCP SDK，Streamable HTTP，固定 https://mcp.mcd.cn。
- `Official.context(storeCode)` 创建到店上下文，**不传 beCode**；麦乐送需要 `delivery=True, be_code=<真实返回编码>`。
- 查询附近门店使用 `beType=1, searchType=2, city, keyword`；默认 searchType=1 会查询收藏门店，不能省略。
- 门店当前营业状态 `businessStatus`；预约能力和日期取 `reservationTimeOptions`。预约时段必须让官方菜单/算价再次验证。
- 当前菜单 `categories[].meals[].code` 与 `meals` 字典连接。菜单 `currentPrice` 是元字符串；官方算价 `price`、`originalPrice`、`discount` 是整数分。
- 营养响应外层为 `success/code/data`，data 为 TOON；字段 productName、energyKcal、protein、fat、carbohydrate、sodium、calcium。能量用 kcal，宏量用 g，钠/钙用 mg。抓取时间不等于官方数据更新时间；后者未提供时写“未知”。
- `menu_items` 仅精确名称/显式别名匹配，不进行模糊替换。`query-meal-detail.rounds` 不为空时必须解析真实组件，不将其当成营养库同名单品。
- `recommend_live` 是受限的自动单品工作流；默认最多24项、6次算价，剔除随单购会员优惠、无营养匹配、含未选择组件的商品。扩展套餐需提供 `bundle()` 求和后的完整原子选择。
- `Official.coupons(context)` 查询三类券，未经明确授权不调用 `claim_coupons`。`coupon_items` 可传用户选择且当前门店适用的券编码，官方校验适用性；空券列表按无券处理。
- 报价外送字段需要明确的费用分项。到店与外送返回均已真实验证；外送原价已含配送/打包费，不能再加一次。未知格式会停止。
- `prepare` 重新计算选中组合价格、核对 productList、确认 takeWayList。返回 OrderPlan 后，向用户展示原始明细，包括 takeWayCode / reservationDate / addressId 所对应的可读信息。
- `OrderService(gateway, Path('private/order-attempts.sqlite'), test_mode=False)` 仅在真实用户明确确认后创建订单；`create(plan, '确认下单 '+plan.digest()[:12])`。
- 测试 fake gateway 必须 `live=False`；生产仅 `connect()`。`create-order` 禁止自动重试；任何不确定结果先通过 `query-order`/官方 App核对。

输出以 `presentation.render` 为起点；补上官方原价、优惠额、配送费、钠钙及券适用范围。若无已确认的热量目标，C方案仅比较营养结构，不能声称实现了减脂热量控制。未经官方算价只能称为暂估。

自然语言触发验收分别记录在 docs/VALIDATION.md；格式验证通过不等于实际自动触发已经验证。

优惠比较：`mcp.coupons.compare_coupon_options`比较无券基线与逐张明确适用券，默认最多6次官方算价，不自动叠券或领券；返回最低应付的商品参数供prepare重新报价。

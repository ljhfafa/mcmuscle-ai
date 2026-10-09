# 麦当劳 MCP 集成

官方服务：https://mcp.mcd.cn，Streamable HTTP，Bearer认证。官方使用文档：https://github.com/M-China/mcd-mcp-server。运行时通过MCP标准initialize与tools/list发现schema，不硬编码未经确认的参数。

|工具|用途|2026-10-09验证状态|
|---|---|---|
|list-nutrition-foods|官方营养数据库|真实只读通过，160行，158个唯一餐品|
|query-nearby-stores|到店门店/营业状态/预约能力|真实只读通过，公开示例城市地标|
|query-meals|当前在售菜单与价格|真实只读通过|
|query-meal-detail|标准餐品及套餐组件详情|真实只读通过；自动标准单品流程|
|available-coupons|查询可领取券|真实只读通过，未领取|
|query-my-coupons|查询已持有券|真实只读通过；测试账户返回空|
|query-store-coupons|门店适用券|真实只读通过；返回空|
|calculate-price|最终报价/费用/取餐方式|真实无券算价通过；折扣逻辑Mock通过|
|delivery-query-addresses|外送地址选择|真实只读通过；私人地址不公开|
|delivery-query-stores|可配送门店|真实只读通过；个人地址对应门店不公开|
|auto-bind-coupons|经授权领取优惠券|已实现明确授权门槛；仅Mock验证|
|create-order|确认后创建待支付订单|已实现；仅Mock验证，未创建真实订单|
|query-order|查询订单状态|已实现；Mock验证，未访问真实订单|

营养来源与价格来源分开：`Official.nutrition`解析API外层JSON中的TOON，`menu_items`与当前门店实际菜单连接；标准营养是每份值，餐品别名必须显式、不能猜尺寸。菜单金额为元字符串，算价金额为整数分。Python营养模块从用户参数计算规划目标；不会让模型在Prompt中算精确数字。

确定性搜索先产生有限候选，保留潜在折后可行组合，再用官方算价筛选并重排。支持将明确适用的券编码放入商品行；不根据券名推算价格或默认叠加，未授权不领券。当前账户无持有券，不能宣称已验证真实优惠核销。外送未知费用格式会拒绝计算，等待已观测字段适配。

订单流程：用户选方案 → `prepare`新鲜算价及餐品核对 → 展示门店/餐品/组件/数量/方式/地址/预约/券/金额 → 用户明确确认 → `OrderService.create` → 返回服务器订单详情和支付链接 → 用户本人支付。测试模式拒绝真实Gateway；订单尝试写入本机摘要日志并消耗一次确认，网络失败也不会盲目重试。

稳定性：官方SDK处理Streamable HTTP及协议会话；参数按实时JSON Schema校验。只读调用有限重试与指数退避，429考虑Retry-After；认证错误明确失败。营养只存进程内1小时缓存、菜单30秒，算价/订单查询不缓存；客户端0.25秒最小请求间隔。无第三方日志/遥测代码，固定官方域名、不跟随认证重定向。

安全：macOS钥匙串隐藏输入，Codex本地HTTP header helper；其他环境用MCD_MCP_TOKEN。示例只含环境变量占位符；CI无Token，Mock与生产分离。隐私字段不写公开演示；创建/领取/积分/抽奖/支付不参与真实测试。

实际价值：将个人单餐规划与可购商品、预算和官方算价连起来，显示蛋白质性价比、目标偏差和数据不足之处，让用户在下单前作出知情选择。

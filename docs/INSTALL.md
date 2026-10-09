# 安装、配置与更新

## 普通用户：macOS + Codex

1. 在项目 GitHub 页面点 Code → Download ZIP，解压到你希望保存的文件夹。需要 Python 3.11+；当前开发环境使用3.11.9。
2. 双击 Install.command。脚本建立项目独立 `.venv`、安装依赖并运行离线演示；不会获取或公开你的 Token。
3. 在 https://open.mcd.cn/mcp 登录 → 控制台。先撤销可能泄露的旧 Token，再生成新 Token。本人完成验证码、服务协议等手续。
4. 双击 Setup Token.command，在本机隐藏输入框粘贴新 Token，点击“安全保存”。钥匙串若询问访问许可，只允许本次项目的 Python。
5. 在 Codex 打开这个项目目录，信任你安装的项目配置；输入“使用麦麦肌肉大王给我配一顿减脂餐”。未显示新 Skill 时重新打开项目或重启 Codex。

当前用户本机已配置全局 mcd 条目；下载项目的新用户由安装器生成项目 `.codex/config.toml`。如同名配置已存在，脚本保留原配置并提示核对，不覆盖无关设置。

## 为什么不写 .env

Codex GUI不一定继承终端环境；`.env`也不会自动改变Codex进程环境。macOS方案用新建的独立钥匙串条目，Codex通过本地`http_headers_helper`读取HTTP认证头。凭证不作为命令参数、不写入shell历史或项目文件。

官方支持的常规环境变量方案：

```toml
[mcp_servers.mcd]
url = "https://mcp.mcd.cn"
bearer_token_env_var = "MCD_MCP_TOKEN"
```

适合已由安全启动器提供该进程环境变量的系统；Python也支持读取该变量。macOS优先读取本项目的新钥匙串条目，以避免复用旧环境凭证。项目提供的是钥匙串替代方案，不会声称设置了全系统环境变量。

`mcp-config.example.json` 的 `${MCD_MCP_TOKEN}` 是脱敏示意，只有客户端实现环境变量展开时才有效。Codex应使用TOML环境变量字段或安装器生成的helper，不能直接假定JSON会展开。官方文档：[Codex MCP](https://developers.openai.com/codex/mcp)、[配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)。

## 命令行与其他系统

```bash
python3 scripts/install.py
.venv/bin/mcmuscle demo
.venv/bin/mcmuscle probe
```

Windows使用`.venv\Scripts\python.exe`和`.venv\Scripts\mcmuscle.exe`；隐藏钥匙串输入仅支持macOS，其他平台由用户的凭证管理器安全提供进程环境变量。核心计算和Mock演示跨平台。

参数模式示例在 `examples/profile.json`。Codex可自动为用户生成参数并调用：

```bash
.venv/bin/mcmuscle demo --profile examples/profile.json
```

真实到店推荐要求先让用户选门店，再使用`live --profile private/profile.json --city <城市> --keyword <地标> --store-code <官方编码>`。这是只读入口，无下单选项。用户不用编写命令，可以直接让Codex使用Skill执行。

## 常见问题

- 401：在官方控制台更新新Token，重新运行Setup Token.command；不要发到聊天。关闭并重新打开MCP连接以刷新缓存。
- 429：等待退避；不要同时运行多个客户端刷请求。Python每客户端最多约240次/分钟，账户总限制600次/分钟，多客户端应共享调用预算。
- 只有营养没有价格：先选择门店，当前菜单及官方算价才能证明价格与可售性。
- 没有过敏安全方案：官方没有完整过敏原信息，不能靠名称猜测，请使用官方渠道核实；程序不会自动放宽你的限制。
- 无可行方案：调整预算或用户明确授权的目标；未知营养、含会员随单购条件和未选择完整组件的套餐被排除。
- 外送费用字段变化：停止算价，需要据官方schema补充费用适配，不能把未知配送费计为0。
- 创建结果不明确：不要重试，先在麦当劳官方App/订单查询核对。

更新：让Codex“更新这个mcmuscle-ai项目并重新运行测试”，或Git用户执行git pull后重新运行Install.command。路径变化后需重新生成helper配置。私人目录`private/`和`.codex/`始终不上传。

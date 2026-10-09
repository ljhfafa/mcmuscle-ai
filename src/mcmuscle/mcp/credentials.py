"""No token files or shell arguments. macOS Keychain or explicitly supplied environment."""

import json
import os
import subprocess
import sys

SERVICE = "McMuscle AI fresh MCP credential v1"
ACCOUNT = "MCD_MCP_TOKEN"


def backend():
    if sys.platform != "darwin":
        raise RuntimeError("此系统请通过私密环境变量 MCD_MCP_TOKEN 配置凭证")
    from keyring.backends.macOS import Keyring

    return Keyring()


def token() -> str:
    value = (
        backend().get_password(SERVICE, ACCOUNT) if sys.platform == "darwin" else None
    ) or os.environ.get(ACCOUNT)
    if not value or any(c.isspace() for c in value):
        raise RuntimeError("未配置新 MCP Token；请运行安全配置，不要发送到聊天")
    return value


def setup() -> None:
    script = """text returned of (display dialog "麦麦肌肉大王：请粘贴刚生成的新 MCP Token。旧 Token 请先在官方控制台撤销。仅保存到本机钥匙串，不会显示在聊天或终端。" default answer "" with hidden answer buttons {"取消", "安全保存"} default button "安全保存" with title "McMuscle 安全配置")"""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("用户取消或系统阻止了安全输入")
    value = result.stdout.strip()
    if len(value) < 16 or any(c.isspace() for c in value):
        raise RuntimeError("输入格式无效，未保存")
    backend().set_password(SERVICE, ACCOUNT, value)
    print("新 Token 已保存至 macOS 钥匙串。未输出凭证。")


def headers() -> None:
    # Only invoke as Codex http_headers_helper; never run this function for diagnostics.
    print(json.dumps({"Authorization": "Bearer " + token()}))


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "headers":
            headers()
        else:
            setup()
    except Exception:
        print("安全凭证配置未完成；未输出敏感诊断。", file=sys.stderr)
        raise SystemExit(1) from None

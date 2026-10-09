"""One entrypoint: install package, discoverable project Skill and safe MCP config."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
venv = root / ".venv"
python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.exists():
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
subprocess.run(
    [str(python), "-m", "pip", "install", "--upgrade", "pip>=26.1.2", "setuptools>=83"], check=True
)
subprocess.run([str(python), "-m", "pip", "install", "-e", f"{root}[live]"], check=True)
config = root / ".codex/config.toml"
config.parent.mkdir(exist_ok=True)
if config.exists():
    print("Existing project Codex config preserved; inspect docs/INSTALL.md before editing.")
else:
    if sys.platform == "darwin":
        # Helper runs locally in the GUI, so no Terminal environment inheritance is required.
        helper = str(root / "src/mcmuscle/mcp/credentials.py")
        content = '[mcp_servers.mcd]\nurl = "https://mcp.mcd.cn"\n'
        content += (
            "http_headers_helper = "
            + json.dumps(shlex.join([str(python), helper, "headers"]))
            + "\n"
        )
    else:
        content = '[mcp_servers.mcd]\nurl = "https://mcp.mcd.cn"\nbearer_token_env_var = "MCD_MCP_TOKEN"\n'
    content += 'disabled_tools = ["create-order", "auto-bind-coupons", "mall-create-order", "draw-lottery", "party-order-create", "delivery-create-address", "cancel-order"]\n'
    config.write_text(content)
    config.chmod(0o600)
subprocess.run([str(python), "-m", "mcmuscle.cli", "demo"], check=True)
print(
    "Installed. Open this project directory in Codex, trust its project config, and invoke $mcmuscle."
)
print(
    "macOS: double-click Setup Token.command for hidden input. No token is written to this project."
)

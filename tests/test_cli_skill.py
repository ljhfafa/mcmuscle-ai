import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_cli_offline_demo():
    r = subprocess.run(
        [sys.executable, "-m", "mcmuscle.cli", "demo"], capture_output=True, text=True
    )
    assert r.returncode == 0 and "MOCK DEMO" in r.stdout
    assert "蛋白质大王" in r.stdout and "省钱肌肉王" in r.stdout and "热量控制王" in r.stdout


def test_simple_profile_entry(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"goal": "cut", "weight_kg": 60, "budget": 30}))
    r = subprocess.run(
        [sys.executable, "-m", "mcmuscle.cli", "demo", "--profile", str(f)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "不计算 BMR/TDEE" in r.stdout


def test_skill_metadata_and_references():
    skill = ROOT / ".agents/skills/mcmuscle"
    text = (skill / "SKILL.md").read_text()
    meta = yaml.safe_load(text.split("---", 2)[1])
    assert meta["name"] == "mcmuscle" and meta["description"]
    assert (skill / "references/workflow.md").is_file()
    ui = yaml.safe_load((skill / "agents/openai.yaml").read_text())
    assert ui["policy"]["allow_implicit_invocation"] is True


def test_example_config_is_placeholder():
    config = json.loads((ROOT / "mcp-config.example.json").read_text())
    assert config["mcpServers"]["mcd"]["headers"]["Authorization"] == "Bearer ${MCD_MCP_TOKEN}"


def test_no_mock_marked_live(tmp_path):
    from mcmuscle.demo import menu

    f = tmp_path / "input.json"
    f.write_text(
        json.dumps({"mock": False, "profile": {"budget": 40}, "items": [menu()[0].model_dump()]})
    )
    r = subprocess.run(
        [sys.executable, "-m", "mcmuscle.cli", "recommend", str(f)], capture_output=True, text=True
    )
    assert r.returncode == 1

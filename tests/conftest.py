import socket

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """CI and unit tests cannot reach real services or reuse host secrets."""
    monkeypatch.delenv("MCD_MCP_TOKEN", raising=False)

    def blocked(*args, **kwargs):
        raise AssertionError("Network is forbidden in automated tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    from mcmuscle.mcp import credentials

    monkeypatch.setattr(credentials, "token", blocked)

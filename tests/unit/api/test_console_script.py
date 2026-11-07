"""Console scripts declared in ``pyproject.toml`` resolve to working entry points."""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from pathlib import Path
from typing import Any

import pytest

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def _console_scripts() -> dict[str, str]:
    """Parse ``[project.scripts]`` without tomllib (unavailable on Python 3.10)."""
    section = PYPROJECT.read_text(encoding="utf-8").split("[project.scripts]", 1)[1]
    section = section.split("\n[", 1)[0]
    return dict(re.findall(r'^([\w-]+)\s*=\s*"([^"]+)"', section, flags=re.MULTILINE))


def _load(target: str) -> Any:
    module_name, _, attribute = target.partition(":")
    return getattr(importlib.import_module(module_name), attribute)


@pytest.mark.parametrize("name", sorted(_console_scripts()))
def test_console_scripts_resolve_import_and_run(
    name: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    entry_point = _load(_console_scripts()[name])

    assert inspect.isfunction(entry_point), f"{name} points at {type(entry_point).__name__}"
    monkeypatch.setattr(sys, "argv", [name, "--help"])
    with pytest.raises(SystemExit) as exit_info:
        entry_point()
    assert exit_info.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_medagent_script_serves_the_api_with_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["medagent", "--host", "127.0.0.2", "--port", "9001"])

    _load(_console_scripts()["medagent"])()

    assert calls == [
        (("medagent.api.main:app",), {"host": "127.0.0.2", "port": 9001, "reload": False})
    ]

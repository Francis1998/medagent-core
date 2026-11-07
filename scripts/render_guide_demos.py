#!/usr/bin/env python3
"""Render guide demo GIFs from REAL runs of each guide's ``python`` example.

Every ``docs/guides/*.md`` guide embeds a demo GIF from ``assets/``. For each
target guide this script:

1. extracts the guide's first fenced ``python`` block (its usage example);
2. executes it verbatim with ``sys.executable`` from the repository root with
   ``PYTHONPATH=src``, a minimal environment (provider API keys forced empty),
   outbound sockets blocked, and a timeout;
3. renders ``$ cat example.py``, ``$ PYTHONPATH=src python example.py`` and the
   captured output into a terminal-style GIF with ``render_transcript_gif.py``,
   written to the path the guide already embeds, so no markdown changes.

Output is never edited or invented. An example that fails, prints nothing but
log lines, times out, or needs the network is reported and not rendered: fix
the guide example instead.

Without arguments the targets are the guides whose embedded GIF is missing or a
placeholder (not a GIF, under 200x100 px, or under 2 KB, the limits enforced by
tests/unit/test_demo_gifs_real.py). Pass guide paths (or GIF paths) to
re-render specific demos.

Usage (Pillow is only needed for rendering, not for --check):
    uv run --with pillow python scripts/render_guide_demos.py
    uv run --with pillow python scripts/render_guide_demos.py docs/guides/WARFARIN_NSAID_GUIDE.md
    python scripts/render_guide_demos.py --check docs/guides/WARFARIN_NSAID_GUIDE.md
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES_DIR = ROOT / "docs" / "guides"

MIN_WIDTH_PX = 200
MIN_HEIGHT_PX = 100
MIN_BYTES = 2048
TIMEOUT_S = 60

COLS = 96
MIN_ROWS = 14
MAX_ROWS = 40
RUN_COMMAND = "PYTHONPATH=src python example.py"

PYTHON_BLOCK = re.compile(r"^```python[ \t]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
GIF_EMBED = re.compile(r"!\[[^\]]*\]\(([^)\s]+\.gif)\)")
LOG_LINE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\S* \[\w+\s*\] ")
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
NETWORK_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+"
    r"(medagent\.(?:llm|retrieval|agent|api)|openai|anthropic|google|httpx|aiohttp"
    r"|requests|urllib|http|socket)\b",
    re.MULTILINE,
)

PROVIDER_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "KIMI_API_KEY",
    "MOONSHOT_API_KEY",
    "PUBMED_API_KEY",
    "OPENFDA_API_KEY",
)
NETWORK_BLOCKED = "network access is disabled while rendering guide demos"

# Runs in the example's interpreter: block outbound sockets, then execute the
# example source (read from stdin) as ``example.py`` in a fresh ``__main__``.
SANDBOX = f"""
import socket
import sys


def _offline(*_args, **_kwargs):
    raise OSError({NETWORK_BLOCKED!r})


_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def _connect_local(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _offline()
    return _connect(self, address)


def _connect_ex_local(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _offline()
    return _connect_ex(self, address)


socket.socket.connect = _connect_local
socket.socket.connect_ex = _connect_ex_local
socket.create_connection = _offline
socket.getaddrinfo = _offline
source = sys.stdin.read()
sys.argv = ["example.py"]
exec(compile(source, "example.py", "exec"), {{"__name__": "__main__", "__file__": "example.py"}})
"""


@dataclass(frozen=True)
class Demo:
    """A guide, the demo GIF it embeds, and the guide's python example."""

    guide: Path
    gif: Path
    code: str | None


def rel(path: Path) -> str:
    """Return ``path`` relative to the repository root, POSIX style."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def gif_problem(path: Path) -> str | None:
    """Return why ``path`` is not a real demo GIF, or ``None`` if it is one."""
    if not path.is_file():
        return "missing"
    data = path.read_bytes()
    if data[:6] not in (b"GIF87a", b"GIF89a") or len(data) < 10:
        return f"not a GIF ({len(data)} bytes)"
    width, height = struct.unpack("<HH", data[6:10])
    if width < MIN_WIDTH_PX or height < MIN_HEIGHT_PX:
        return f"{width}x{height} px placeholder"
    if len(data) < MIN_BYTES:
        return f"{len(data)}-byte placeholder"
    return None


def guide_demos(guide: Path) -> list[Demo]:
    """Return one ``Demo`` per GIF embedded in ``guide``."""
    text = guide.read_text(encoding="utf-8")
    block = PYTHON_BLOCK.search(text)
    code = block.group(1) if block else None
    return [
        Demo(guide=guide, gif=(guide.parent / target).resolve(), code=code)
        for target in dict.fromkeys(GIF_EMBED.findall(text))
        if "://" not in target
    ]


def select_demos(targets: list[str]) -> list[Demo]:
    """Resolve CLI targets (guides or GIFs) to demos; default to placeholder GIFs."""
    every = [demo for guide in sorted(GUIDES_DIR.glob("*.md")) for demo in guide_demos(guide)]
    if not targets:
        chosen = [demo for demo in every if gif_problem(demo.gif)]
    else:
        chosen = []
        for target in targets:
            path = Path(target).resolve()
            if path.suffix == ".md":
                if path.parent != GUIDES_DIR:
                    raise SystemExit(f"error: {target} is not a docs/guides/*.md guide")
                matches = guide_demos(path)
            else:
                matches = [demo for demo in every if demo.gif == path]
            if not matches:
                raise SystemExit(f"error: no guide demo GIF found for {target}")
            chosen += matches
    unique: dict[Path, Demo] = {}
    for demo in chosen:
        unique.setdefault(demo.gif, demo)
    return list(unique.values())


def offline_env() -> dict[str, str]:
    """Return a minimal environment with provider keys blanked (overrides ``.env``)."""
    env = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT") if key in os.environ}
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
            "NO_COLOR": "1",
            "TZ": "UTC",
        }
    )
    env.update(dict.fromkeys(PROVIDER_KEYS, ""))
    return env


def run_example(code: str) -> tuple[list[str], str | None]:
    """Execute an example offline; return its output lines and any problem."""
    match = NETWORK_IMPORT.search(code)
    if match:
        return [], f"needs network (imports {match.group(1)}); not run"
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv; the code is the repo's own guide
            [sys.executable, "-c", SANDBOX],
            input=code,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            cwd=ROOT,
            env=offline_env(),
            timeout=TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [], f"timed out after {TIMEOUT_S} s"
    lines = [ANSI_ESCAPE.sub("", line).rstrip() for line in completed.stdout.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    if NETWORK_BLOCKED in completed.stdout:
        return lines, "needs network (blocked socket access)"
    if completed.returncode != 0:
        last = lines[-1] if lines else "no output"
        return lines, f"exited {completed.returncode}: {last}"
    if not any(line and not LOG_LINE.match(line) for line in lines):
        return lines, "prints nothing besides log lines; print the documented result"
    return lines, None


def transcript(code: str, output: list[str]) -> list[str]:
    """Build the terminal transcript: show the example, then run it."""
    return ["$ cat example.py", *code.rstrip("\n").splitlines(), f"$ {RUN_COMMAND}", *output]


def render(demo: Demo, lines: list[str]) -> str:
    """Render ``lines`` into ``demo.gif``; return a short summary."""
    from render_transcript_gif import render_transcript, wrap_lines  # needs Pillow

    rows = min(MAX_ROWS, max(MIN_ROWS, len(wrap_lines(lines, COLS)) + 1))
    frames = render_transcript(
        lines,
        demo.gif,
        title=f"medagent-core: {rel(demo.guide)}",
        cols=COLS,
        rows=rows,
        type_steps=6,
        final_hold_ms=6000,
        block_output=True,
        fixed_palette=True,
    )
    data = demo.gif.read_bytes()
    width, height = struct.unpack("<HH", data[6:10])
    return f"{len(data):,} bytes, {width}x{height} px, {frames} frames"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("targets", nargs="*", help="guide .md files or embedded demo GIFs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the examples and validate their output without rendering",
    )
    args = parser.parse_args()

    demos = select_demos(args.targets)
    if not demos:
        print("no placeholder demo GIFs found; pass guide paths to re-render specific demos")
        return 0

    failures = 0
    for demo in demos:
        if demo.code is None:
            problem: str | None = "has no ```python example"
            output: list[str] = []
        else:
            output, problem = run_example(demo.code)
        if problem:
            failures += 1
            print(f"FAILED {rel(demo.guide)}: {problem}")
            continue
        assert demo.code is not None
        if args.check:
            print(f"ok     {rel(demo.guide)} -> {rel(demo.gif)} ({len(output)} output lines)")
            continue
        summary = render(demo, transcript(demo.code, output))
        print(f"wrote  {rel(demo.gif)} from {rel(demo.guide)} ({summary})")

    total = len(demos)
    verb = "checked" if args.check else "rendered"
    print(f"{total - failures}/{total} guide demos {verb}; {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

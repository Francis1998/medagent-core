"""Every GIF embedded in README/docs markdown must be a real, visible demo.

66 guide demos once shipped as 1x1-pixel or empty placeholder GIFs, so readers
saw nothing where a guide promised a demo. Re-render a guide demo from the
guide's own example with ``scripts/render_guide_demos.py`` (see CONTRIBUTING.md).
"""

from __future__ import annotations

import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MIN_WIDTH_PX = 200
MIN_HEIGHT_PX = 100
MIN_BYTES = 2048

GIF_REF = re.compile(
    r"!\[[^\]]*\]\(\s*<?([^)\s>]+\.gif)>?(?:\s+\"[^\"]*\")?\s*\)"
    r"|<img\b[^>]*\bsrc=[\"']([^\"']+\.gif)[\"']",
    re.IGNORECASE,
)

# Byte-for-byte the 43-byte placeholder that shipped as e.g. acei_sacubitril_demo.gif.
ONE_PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00"
    b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def gif_problem(data: bytes | None) -> str | None:
    """Return why ``data`` is not a real demo GIF, or ``None`` when it is one."""
    if data is None:
        return "missing"
    if data[:6] not in (b"GIF87a", b"GIF89a") or len(data) < 10:
        return f"not a GIF ({len(data)} bytes)"
    width, height = struct.unpack("<HH", data[6:10])
    if width < MIN_WIDTH_PX or height < MIN_HEIGHT_PX:
        return f"{width}x{height} px (< {MIN_WIDTH_PX}x{MIN_HEIGHT_PX})"
    if len(data) < MIN_BYTES:
        return f"{len(data)} bytes (< {MIN_BYTES})"
    return None


def _gif_refs() -> dict[Path, list[str]]:
    """Map each locally embedded GIF to the markdown lines that embed it."""
    refs: dict[Path, list[str]] = {}
    for md in sorted({*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md")}):
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for match in GIF_REF.finditer(line):
                target = match.group(1) or match.group(2)
                if "://" in target:
                    continue
                gif = (md.parent / target).resolve()
                refs.setdefault(gif, []).append(f"{md.relative_to(ROOT).as_posix()}:{lineno}")
    return refs


def test_scan_covers_readme_catalog_and_guides() -> None:
    """The guard must actually see the README, catalog, and guide embeds."""
    refs = _gif_refs()
    sources = {ref.split(":")[0] for places in refs.values() for ref in places}

    assert len(refs) > 250
    assert "README.md" in sources
    assert "docs/SAFETY_PANEL_CATALOG.md" in sources
    assert ROOT / "assets" / "acei_arb_duplication_demo.gif" in refs
    assert ROOT / "assets" / "mcp_server_demo.gif" in refs


def test_detector_rejects_placeholders() -> None:
    """1x1, empty, non-GIF, and tiny files are all rejected; real headers pass."""
    real_header = b"GIF89a" + struct.pack("<HH", 800, 342) + b"\x00" * 4000

    assert gif_problem(None) == "missing"
    assert gif_problem(b"") == "not a GIF (0 bytes)"
    assert gif_problem(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4000) is not None
    assert gif_problem(ONE_PIXEL_GIF) == "1x1 px (< 200x100)"
    assert gif_problem(real_header[:1500]) == "1500 bytes (< 2048)"
    assert gif_problem(real_header) is None


def test_embedded_gifs_are_real_demos() -> None:
    """No markdown-embedded GIF may be missing, invalid, tiny, or a placeholder."""
    offenders = []
    for gif, places in sorted(_gif_refs().items()):
        problem = gif_problem(gif.read_bytes() if gif.is_file() else None)
        if problem:
            offenders.append(f"{gif.relative_to(ROOT).as_posix()}: {problem} ({places[0]})")

    assert offenders == [], (
        f"{len(offenders)} embedded demo GIFs are placeholders; re-render them with "
        "scripts/render_guide_demos.py:\n" + "\n".join(offenders)
    )


def test_guide_demo_generator_runs_examples_offline() -> None:
    """--check runs real guide examples (no network, no Pillow) and finds output."""
    guides = [
        "docs/guides/ACEI_POTASSIUM_GUIDE.md",
        "docs/guides/WARFARIN_NSAID_GUIDE.md",
        "docs/guides/DIGOXIN_TOXICITY_GUIDE.md",
    ]
    completed = subprocess.run(
        [sys.executable, "scripts/render_guide_demos.py", "--check", *guides],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "3/3 guide demos checked; 0 failed" in completed.stdout
    for guide in guides:
        assert f"ok     {guide} -> assets/" in completed.stdout

"""Guard user-facing prose against retired model-stack boilerplate.

Guides, SVG demos, docstrings, and runtime finding messages used to recommend
"GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2" long after the configured
defaults moved to GPT-6.1 Sol, Claude Opus 5.5, Gemini 4 Argon, and Kimi K3.1 Pro.
CONFIGURATION.md keeps a deliberate legacy-model behaviour table, and historical
records (CHANGELOG, daily logs, release notes, ADRs) are exempt; tests are not
scanned.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RETIRED_PROSE = re.compile(
    r"\bGPT-5\.5\b|\bGPT-4o\b|\bClaude\s+(?:Sonnet|Opus)\s+4\.\d\b"
    r"|\bSonnet\s+4\.6\b|\bKimi\s+K2\b(?!\.\d)|\bGemini\s+2\.5\b"
)

EXEMPT = {
    Path("CHANGELOG.md"),
    Path("CONFIGURATION.md"),
    Path("DAILY_IMPROVEMENTS.md"),
}
EXEMPT_DIRS = {Path("docs/releases"), Path("docs/adr")}


def _prose_files() -> list[Path]:
    """Return the user-facing docs, SVG demos, and non-test sources to scan."""
    files = [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md"), *ROOT.glob("assets/*.svg")]
    files += [*ROOT.glob("src/**/*.py"), *ROOT.glob("scripts/**/*.py")]
    return sorted(
        p
        for p in files
        if p.relative_to(ROOT) not in EXEMPT
        and not any(parent in EXEMPT_DIRS for parent in p.relative_to(ROOT).parents)
    )


def test_scan_covers_guides_sources_and_demos() -> None:
    """The guard must actually see the guides, safety modules, and SVG demos."""
    rels = {p.relative_to(ROOT).as_posix() for p in _prose_files()}

    assert "README.md" in rels
    assert "assets/demo_llm_routing.svg" in rels
    assert "src/medagent/reasoning/soap_structurer.py" in rels
    assert sum(r.startswith("docs/guides/") for r in rels) > 100


def test_no_retired_model_stack_in_prose() -> None:
    """Docs, demos, and finding messages name the current model stack."""
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:120]}"
        for path in _prose_files()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if RETIRED_PROSE.search(line)
    ]

    assert offenders == [], "retired model names in prose:\n" + "\n".join(offenders[:40])

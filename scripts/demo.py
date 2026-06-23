"""Interactive rich-terminal demo of the medagent-core pipeline.

Simulates a full agent run with pre-canned clinical cases so the demo
runs without any LLM API keys or external network access.

Usage:
    python scripts/demo.py                          # default: chest pain MI case
    python scripts/demo.py --case drug_interaction  # polypharmacy interaction case
    python scripts/demo.py --case escalate          # ambiguous presentation -> ESCALATE
    python scripts/demo.py --case all               # cycle through all three cases
    python scripts/demo.py --no-delay               # skip animation delays (for CI)
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console(highlight=False)
DELAY = 0.4


CASES: dict[str, dict[str, Any]] = {
    "chest_pain_mi": {
        "title": "STEMI — Chest Pain with Elevated Troponin",
        "patient": {
            "age": 65,
            "sex": "male",
            "chief_complaint": "Crushing chest pain radiating to left arm, diaphoresis",
            "clinical_notes": (
                "65M presents with 2h history of crushing substernal chest pain radiating "
                "to left arm. ECG: ST elevation II, III, aVF. Troponin-I 2.4 ng/mL."
            ),
            "medications": ["aspirin 81mg", "metoprolol 25mg", "atorvastatin 40mg"],
            "labs": {
                "Troponin-I": "2.4 ng/mL [HIGH]",
                "BNP": "340 pg/mL [HIGH]",
                "Creatinine": "1.1 mg/dL [normal]",
            },
        },
        "entities": [
            ("chest pain", "DISEASE"),
            ("myocardial infarction", "DISEASE"),
            ("shortness of breath", "DISEASE"),
            ("aspirin", "CHEMICAL"),
            ("metoprolol", "CHEMICAL"),
            ("atorvastatin", "CHEMICAL"),
            ("troponin", "GENE"),
            ("hypertension", "DISEASE"),
        ],
        "docs": [
            ("PubMed", "36271026", "Troponin kinetics in STEMI diagnosis", 0.92),
            ("PubMed", "35814523", "High-sensitivity troponin 0/1h rule-out algorithm", 0.87),
            ("LocalKB", "kb_004", "Myocardial Infarction — Biomarkers", 0.85),
            ("LocalKB", "kb_001", "ST Elevation MI — ECG criteria and management pathway", 0.81),
        ],
        "interaction": (
            "aspirin",
            "metoprolol",
            "MODERATE",
            "Additive bradycardia risk",
            ["rxnorm", "openfda"],
        ),
        "hypotheses": [
            (
                "STEMI — Inferior Wall",
                "I21.19",
                0.891,
                [
                    ("FOR", "Markedly elevated troponin-I (2.4 ng/mL)", 0.95),
                    ("FOR", "ST elevation in inferior leads II/III/aVF", 0.92),
                    ("FOR", "Typical radiation pattern to left arm", 0.82),
                ],
                [
                    ("AGAINST", "No documentation of prior cath/stent", 0.3),
                ],
                None,
            ),
            (
                "NSTEMI",
                "I21.4",
                0.612,
                [
                    ("FOR", "Elevated troponin consistent with myocardial injury", 0.75),
                ],
                [
                    ("AGAINST", "ST elevation localises to STEMI, not NSTEMI pattern", 0.80),
                ],
                "Distinguish via STEMI vs NSTEMI criteria",
            ),
            (
                "Aortic Dissection",
                "I71.00",
                0.341,
                [
                    ("FOR", "Severe acute chest pain in hypertensive patient", 0.55),
                ],
                [
                    ("AGAINST", "No pulse differential, no widened mediastinum documented", 0.85),
                    ("AGAINST", "Troponin elevation more consistent with ACS", 0.70),
                ],
                "Requires CT-angiography to exclude definitively",
            ),
        ],
        "confidence": 0.81,
        "escalated": False,
        "next_steps": [
            "Immediate cardiology consult for primary PCI consideration",
            "Dual antiplatelet therapy (aspirin + P2Y12 inhibitor) per ACS protocol",
            "Serial troponin measurements at 3h and 6h intervals",
            "Monitor for aspirin + metoprolol interaction — bradycardia risk MODERATE",
        ],
    },
    "drug_interaction": {
        "title": "Polypharmacy — High-Risk Drug Combination Screening",
        "patient": {
            "age": 78,
            "sex": "female",
            "chief_complaint": "Medication reconciliation: warfarin + amiodarone co-prescription",
            "clinical_notes": (
                "78F with AF on warfarin (INR target 2.0-3.0). Cardiologist initiated "
                "amiodarone for refractory AF. Also on aspirin 81mg and omeprazole 20mg."
            ),
            "medications": ["warfarin 5mg", "amiodarone 200mg", "aspirin 81mg", "omeprazole 20mg"],
            "labs": {"INR": "2.3 [therapeutic]", "Creatinine": "1.2 mg/dL"},
        },
        "entities": [
            ("warfarin", "CHEMICAL"),
            ("amiodarone", "CHEMICAL"),
            ("aspirin", "CHEMICAL"),
            ("omeprazole", "CHEMICAL"),
            ("atrial fibrillation", "DISEASE"),
        ],
        "docs": [
            (
                "PubMed",
                "34521987",
                "Amiodarone-warfarin interaction: INR monitoring protocol",
                0.95,
            ),
            ("OpenFDA", "warfarin-label", "FDA warfarin label: amiodarone interaction", 0.91),
            ("LocalKB", "kb_002", "Warfarin Drug Interactions — CYP2C9/2C19 pathways", 0.88),
        ],
        "interactions": [
            (
                "warfarin",
                "amiodarone",
                "CRITICAL",
                "CYP2C9 inhibition — 3-5x INR elevation — life-threatening bleeding",
                ["rxnorm", "openfda"],
            ),
            (
                "warfarin",
                "aspirin",
                "MODERATE",
                "Additive anticoagulation + GI mucosal damage",
                ["rxnorm", "openfda"],
            ),
            (
                "omeprazole",
                "warfarin",
                "MODERATE",
                "CYP2C19 inhibition modestly increases warfarin AUC",
                ["rxnorm", "openfda"],
            ),
        ],
        "confidence": 0.72,
        "escalated": False,
        "next_steps": [
            "Urgent INR monitoring — amiodarone will increase INR 3-5x over 2-6 weeks",
            "Reduce warfarin dose by 30-50% empirically when starting amiodarone",
            "Add PPI cover (already prescribed omeprazole) given aspirin co-prescription",
            "Weekly INR checks for first 3 months of amiodarone therapy",
        ],
    },
    "escalate": {
        "title": "Ambiguous B-Symptoms — ESCALATE Triggered",
        "patient": {
            "age": 42,
            "sex": "female",
            "chief_complaint": "Unexplained fatigue, night sweats, 8kg weight loss over 3 months",
            "clinical_notes": (
                "42F with 3-month history of progressive fatigue, drenching night sweats, "
                "and 8kg unintentional weight loss. No localising symptoms. No known exposures."
            ),
            "medications": ["none"],
            "labs": {
                "Hemoglobin": "11.2 g/dL [LOW]",
                "LDH": "Not available",
                "HIV": "Not tested",
            },
        },
        "entities": [
            ("fatigue", "DISEASE"),
            ("night sweats", "DISEASE"),
            ("weight loss", "DISEASE"),
            ("anemia", "DISEASE"),
        ],
        "docs": [
            ("PubMed", "33921045", "B-symptom triad: lymphoma workup guidelines", 0.78),
            ("PubMed", "32145678", "Constitutional symptoms: differential approach", 0.71),
        ],
        "hypotheses": [
            (
                "Lymphoma (B-cell)",
                "C85.90",
                0.421,
                [
                    ("FOR", "Classic B-symptom triad: fever, night sweats, weight loss", 0.80),
                    ("FOR", "Anaemia may indicate marrow involvement", 0.60),
                ],
                [
                    ("AGAINST", "No lymphadenopathy or organomegaly documented", 0.85),
                    ("AGAINST", "LDH unavailable — cannot assess tumour burden", 0.70),
                ],
                "B-cell lymphoma cannot be confirmed without biopsy and PET-CT",
            ),
            (
                "Tuberculosis (active)",
                "A15.9",
                0.389,
                [
                    ("FOR", "Night sweats and weight loss are classic TB B-symptoms", 0.75),
                ],
                [
                    ("AGAINST", "No cough documented, no known TB exposure history", 0.80),
                ],
                "Mantoux/IGRA and chest imaging required",
            ),
            (
                "Chronic Fatigue Syndrome",
                "G93.3",
                0.312,
                [
                    ("FOR", "Prominent fatigue pattern over months", 0.55),
                ],
                [
                    ("AGAINST", "8kg weight loss and night sweats are atypical for CFS", 0.90),
                ],
                "Weight loss and night sweats mandate ruling out organic pathology first",
            ),
            (
                "HIV (late stage)",
                "B24",
                0.298,
                [
                    ("FOR", "Constitutional symptoms consistent with AIDS-defining illness", 0.65),
                ],
                [
                    ("AGAINST", "No risk factors documented in history", 0.55),
                ],
                "HIV test not performed — essential to exclude",
            ),
        ],
        "confidence": 0.38,
        "escalated": True,
        "uncertainty_flags": [
            "Overall confidence 0.38 below threshold 0.60",
            "Strong FOR and AGAINST evidence on top hypothesis — contradictory",
            "Critical investigations unavailable (LDH, HIV, LFTs)",
        ],
        "next_steps": [
            "Refer to a board-certified clinician for immediate evaluation",
            "Essential workup: LDH, ESR/CRP, LFTs, HIV serology, IGRA",
            "Imaging: CT chest/abdomen/pelvis with contrast",
            "Consider haematology referral if lymphoma cannot be excluded",
        ],
    },
}


def sleep(seconds: float) -> None:
    """Conditional sleep respecting the global DELAY flag."""
    if DELAY > 0:
        time.sleep(seconds * DELAY / 0.4)


def render_header(case_title: str) -> None:
    """Print the medagent ASCII banner and case title."""
    banner = Text()
    banner.append(
        "  ███╗   ███╗███████╗██████╗  █████╗  ██████╗ ███████╗███╗   ██╗████████╗\n",
        style="bold cyan",
    )
    banner.append(
        "  ████╗ ████║██╔════╝██╔══██╗██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝\n",
        style="bold cyan",
    )
    banner.append(
        "  ██╔████╔██║█████╗  ██║  ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   \n",
        style="bold blue",
    )
    banner.append(
        "  ██║╚██╔╝██║██╔══╝  ██║  ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   \n",
        style="bold blue",
    )
    banner.append(
        "  ██║ ╚═╝ ██║███████╗██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   \n",
        style="bold magenta",
    )
    banner.append(
        "  ╚═╝     ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   \n",
        style="bold magenta",
    )
    banner.append(
        "                     C O R E  —  clinical reasoning agent\n",
        style="dim italic",
    )
    console.print(banner)
    console.print(Rule(f"[bold yellow]{case_title}[/]"))
    sleep(0.5)


def render_intake(patient: dict[str, Any]) -> None:
    """Display the INTAKE state output."""
    console.print()
    console.print(Rule("[bold blue]◆ INTAKE[/]"))
    sleep(1)
    info = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
    info.add_column("key", style="dim", min_width=18)
    info.add_column("val", style="white")
    info.add_row("Chief complaint", f"[bold]{patient['chief_complaint']}[/]")
    info.add_row("Age / sex", f"{patient['age']} / {patient['sex']}")
    info.add_row("Medications", "  ·  ".join(patient["medications"]))
    for k, v in patient.get("labs", {}).items():
        color = "red" if ("HIGH" in v or "LOW" in v) else "green"
        info.add_row(f"Lab: {k}", f"[{color}]{v}[/]")
    console.print(info)
    sleep(0.8)


def render_extraction(entities: list[tuple[str, str]]) -> None:
    """Display ENTITY_EXTRACTION results."""
    console.print()
    console.print(Rule("[bold blue]◆ ENTITY EXTRACTION[/]"))
    sleep(0.8)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        progress.add_task("[cyan]Running scispaCy NER …", total=None)
        time.sleep(0.6 if DELAY > 0 else 0)
        progress.stop()
    grouped: dict[str, list[str]] = {}
    for text, label in entities:
        grouped.setdefault(label, []).append(text)
    label_colors = {
        "DISEASE": "red",
        "CHEMICAL": "yellow",
        "GENE": "cyan",
        "PROTEIN": "magenta",
    }
    table = Table(show_header=True, header_style="bold dim", box=box.SIMPLE)
    table.add_column("Type", style="bold", min_width=12)
    table.add_column("Entities")
    for label, texts in grouped.items():
        color = label_colors.get(label, "white")
        table.add_row(
            f"[{color}]{label}[/]",
            "  ·  ".join(f"[{color}]{t}[/]" for t in texts),
        )
    console.print(table)
    console.print(f"  [green]✓[/] {len(entities)} entities extracted [dim](0.31s)[/]")
    sleep(0.8)


def render_retrieval(
    docs: list[tuple[str, str, str, float]],
    interaction: tuple[str, str, str, str, list[str]] | None = None,
) -> None:
    """Display KNOWLEDGE_RETRIEVAL results."""
    console.print()
    console.print(Rule("[bold blue]◆ KNOWLEDGE RETRIEVAL[/]"))
    sleep(0.6)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        p1 = progress.add_task("[cyan]PubMed ESearch …", total=100)
        p2 = progress.add_task("[yellow]RxNorm + OpenFDA …", total=100)
        p3 = progress.add_task("[magenta]Local KB hybrid …", total=100)
        for _ in range(10):
            progress.update(p1, advance=10)
            progress.update(p2, advance=8)
            progress.update(p3, advance=12)
            time.sleep(0.06 if DELAY > 0 else 0)
        progress.stop()
    table = Table(show_header=True, header_style="bold dim", box=box.SIMPLE)
    table.add_column("Source", min_width=10)
    table.add_column("ID", style="dim", min_width=10)
    table.add_column("Title", min_width=42)
    table.add_column("Relevance", justify="right")
    for source, doc_id, title, score in docs:
        color = "cyan" if source == "PubMed" else ("magenta" if source == "LocalKB" else "yellow")
        bar = "█" * int(score * 10)
        table.add_row(
            f"[{color}]{source}[/]",
            doc_id,
            title[:48],
            f"[green]{bar}[/] {score:.2f}",
        )
    console.print(table)
    if interaction:
        drug_a, drug_b, severity, mechanism, sources = interaction
        sev_color = {
            "CRITICAL": "red",
            "HIGH": "red",
            "MODERATE": "yellow",
            "LOW": "green",
        }.get(severity, "white")
        console.print(
            Panel(
                f"[bold]{drug_a}[/] + [bold]{drug_b}[/]: [bold {sev_color}]{severity}[/]\n"
                f"[dim]{mechanism}[/]\n"
                f"[green]✓ validated — sources: {', '.join(sources)}[/]",
                title="[bold yellow]Drug Interaction Flagged[/]",
                border_style="yellow",
                expand=False,
            )
        )
    sleep(0.8)


def render_reasoning(
    hypotheses: list[tuple[str, str | None, float, list[Any], list[Any], str | None]],
) -> None:
    """Display REASONING results with Bayesian confidence bars."""
    console.print()
    console.print(Rule("[bold blue]◆ REASONING[/]"))
    sleep(0.6)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as p:
        p.add_task("[cyan]Routing to Claude Sonnet 4.6 ...", total=None)
        time.sleep(1.2 if DELAY > 0 else 0)
        p.stop()
    for i, (label, icd, score, ev_for, ev_against, note) in enumerate(hypotheses, 1):
        score_color = "green" if score >= 0.7 else ("yellow" if score >= 0.5 else "red")
        bar = "█" * int(score * 16) + "░" * (16 - int(score * 16))
        header = Text()
        header.append(f"  #{i} ", style="bold dim")
        header.append(f"{label}", style=f"bold {score_color}")
        if icd:
            header.append(f"  [{icd}]", style="dim")
        header.append(f"  {bar} ", style=score_color)
        header.append(f"{score:.3f}", style=f"bold {score_color}")
        console.print(header)
        for _, stmt, strength in ev_for:
            console.print(f"      [green]+[/] {stmt} [dim]({strength:.0%})[/]")
        for _, stmt, strength in ev_against:
            console.print(f"      [red]-[/] {stmt} [dim]({strength:.0%})[/]")
        if note:
            console.print(f"      [dim italic]note: {note}[/]")
        sleep(0.4)


def render_safety_check(
    confidence: float,
    escalated: bool,
    flags: list[str] | None = None,
) -> None:
    """Display SAFETY_CHECK gate outcome."""
    console.print()
    console.print(Rule("[bold blue]◆ SAFETY CHECK[/]"))
    sleep(0.5)
    threshold = 0.60
    conf_color = "green" if confidence >= threshold else "red"
    bar = "█" * int(confidence * 20) + "░" * (20 - int(confidence * 20))
    console.print(
        f"  Overall confidence: [{conf_color}]{bar}[/] [{conf_color}]{confidence:.2f}[/]  "
        f"[dim]threshold={threshold:.2f}[/]"
    )
    sleep(0.4)
    if flags:
        for flag in flags:
            console.print(f"  [yellow]⚠[/] {flag}")
        sleep(0.3)
    if escalated:
        console.print()
        console.print(
            Panel(
                "[bold red]ESCALATE TRIGGERED[/]\n\n"
                "Confidence below threshold + contradictory evidence detected.\n"
                "Agent halted. [bold]No clinical recommendation produced.[/]\n"
                "Human expert review is [bold underline]required[/] before proceeding.",
                title="[bold red]⚡ ESCALATE[/]",
                border_style="red",
            )
        )
    else:
        console.print(f"  [green]✓ OUTPUT — confidence {confidence:.2f} >= {threshold:.2f}[/]")
    sleep(0.6)


def render_output(
    case: dict[str, Any],
    session_id: str = "b7f3a2c1-9d4e-41ab-8f7c-3e2d1a0b5f6e",
) -> None:
    """Display final ClinicalReasoning output."""
    console.print()
    title = (
        "[bold green]◆ OUTPUT[/]" if not case["escalated"] else "[bold red]◆ ESCALATED OUTPUT[/]"
    )
    console.print(Rule(title))
    sleep(0.5)
    next_steps = case.get("next_steps", [])
    steps_text = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(next_steps))
    color = "green" if not case["escalated"] else "red"
    console.print(
        Panel(
            f"[dim]session_id:[/] {session_id}\n"
            f"[dim]escalated: [/][bold {color}]{case['escalated']}[/]   "
            f"[dim]confidence:[/] [bold {color}]{case['confidence']:.2f}[/]\n\n"
            + (f"[bold]Recommended next steps:[/]\n{steps_text}" if next_steps else ""),
            title="[bold]ClinicalReasoning Result[/]",
            border_style=color,
        )
    )
    sleep(0.5)
    console.print(
        Panel(
            "[bold yellow]WARNING — RESEARCH USE ONLY[/]\n"
            "This output has NOT been reviewed by a licensed clinician. "
            "It is NOT FDA-cleared and MUST NOT be used to guide clinical treatment decisions. "
            "Always consult a qualified healthcare professional.",
            border_style="yellow",
            expand=True,
        )
    )


def run_chest_pain(case: dict[str, Any]) -> None:
    """Run the STEMI chest pain case."""
    render_header(case["title"])
    render_intake(case["patient"])
    render_extraction(case["entities"])
    render_retrieval(case["docs"], interaction=case.get("interaction"))
    render_reasoning(case["hypotheses"])
    render_safety_check(case["confidence"], case["escalated"])
    render_output(case)


def run_drug_interaction(case: dict[str, Any]) -> None:
    """Run the polypharmacy drug interaction case."""
    render_header(case["title"])
    render_intake(case["patient"])
    render_extraction(case["entities"])
    console.print()
    console.print(Rule("[bold yellow]◆ DRUG INTERACTIONS DETECTED[/]"))
    sleep(0.6)
    for drug_a, drug_b, severity, mechanism, sources in case["interactions"]:
        sev_color = {"CRITICAL": "red", "HIGH": "red", "MODERATE": "yellow"}.get(severity, "green")
        console.print(
            Panel(
                f"[bold]{drug_a}[/] + [bold]{drug_b}[/]\n"
                f"[bold {sev_color}]{severity}[/]  {mechanism}\n"
                f"[green]validated: {', '.join(sources)}[/]",
                border_style=sev_color,
                expand=False,
            )
        )
        sleep(0.3)
    render_safety_check(case["confidence"], case["escalated"])
    render_output(case, session_id="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a")


def run_escalate(case: dict[str, Any]) -> None:
    """Run the ambiguous B-symptoms case."""
    render_header(case["title"])
    render_intake(case["patient"])
    render_extraction(case["entities"])
    render_retrieval(case["docs"])
    render_reasoning(case["hypotheses"])
    render_safety_check(
        case["confidence"],
        case["escalated"],
        flags=case.get("uncertainty_flags"),
    )
    render_output(case, session_id="e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b")


RUNNERS = {
    "chest_pain_mi": run_chest_pain,
    "drug_interaction": run_drug_interaction,
    "escalate": run_escalate,
}


async def main() -> None:
    """Entry point — parse args and dispatch to case runners."""
    parser = argparse.ArgumentParser(description="medagent-core interactive demo")
    parser.add_argument(
        "--case",
        choices=[*list(RUNNERS.keys()), "all"],
        default="chest_pain_mi",
    )
    parser.add_argument("--no-delay", action="store_true")
    args = parser.parse_args()
    global DELAY
    if args.no_delay:
        DELAY = 0
    cases_to_run = list(RUNNERS.keys()) if args.case == "all" else [args.case]
    for case_key in cases_to_run:
        RUNNERS[case_key](CASES[case_key])
        if args.case == "all" and case_key != cases_to_run[-1]:
            console.print()
            console.print(Rule("[dim]next case[/]"))
            sleep(2)
    console.print()
    console.print(Rule("[dim]demo complete[/]"))


if __name__ == "__main__":
    asyncio.run(main())

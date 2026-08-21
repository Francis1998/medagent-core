"""Tests for the sildenafil + nitrate critical hypotension checker."""

from medagent.models import Medication, Severity, SildenafilNitrateRisk
from medagent.safety import SildenafilNitrateChecker as ExportedChecker
from medagent.safety.sildenafil_nitrate_checker import SildenafilNitrateChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = SildenafilNitrateChecker()
    assert checker.check(_meds("Sildenafil 50 mg")) == []
    assert checker.check(_meds("Nitroglycerin 0.4 mg SL")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = SildenafilNitrateChecker().check(
        _meds("Sildenafil 50 mg", "Nitroglycerin 0.4 mg SL")
    )[0]

    assert isinstance(finding, SildenafilNitrateRisk)
    assert finding.agent == "sildenafil"
    assert finding.partner_agent == "nitroglycerin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "profound, life-threatening hypotension" in finding.rationale


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["sildenafil", "viagra", "revatio"]:
        finding = SildenafilNitrateChecker().check(
            _meds(f"{primary_agent} dose", "Nitroglycerin 0.4 mg SL")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent in ["nitroglycerin", "isosorbide", "imdur", "monoket"]:
        finding = SildenafilNitrateChecker().check(
            _meds("Sildenafil 50 mg", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = SildenafilNitrateChecker()
    for agent in ["Amlodipine", "Hydralazine", "Ranolazine"]:
        assert checker.check(_meds("Sildenafil 50 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = SildenafilNitrateChecker()
    assert checker.check(_meds("Sildenafillike", "Nitroglycerinfree")) == []
    assert len(checker.check(_meds("Revatio", "Monoket"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Nitroglycerin SL", "Sildenafil 50 mg", "Imdur 30 mg"]
    forward = SildenafilNitrateChecker().check(_meds(*names))
    reverse = SildenafilNitrateChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["imdur", "nitroglycerin"]
    assert (
        len(
            SildenafilNitrateChecker().check(
                _meds(
                    "Sildenafil 50 mg",
                    "Sildenafil 50 mg",
                    "Nitroglycerin 0.4 mg SL",
                    "Nitroglycerin 0.4 mg SL",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert SildenafilNitrateChecker().check(_meds("Revatio and Monoket interaction warning")) == []
    finding = ExportedChecker().check(_meds("Revatio", "Monoket"))[0]
    assert finding.severity is Severity.CRITICAL

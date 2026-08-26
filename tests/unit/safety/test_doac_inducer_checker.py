"""Tests for the DOAC + strong inducer thrombosis-risk checker."""

from medagent.models import DoacInducerRisk, Medication, Severity
from medagent.safety import DoacInducerChecker as ExportedChecker
from medagent.safety.doac_inducer_checker import DoacInducerChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = DoacInducerChecker()
    assert checker.check(_meds("Apixaban 5 mg")) == []
    assert checker.check(_meds("Rifampin 600 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = DoacInducerChecker().check(_meds("Apixaban 5 mg", "Rifampin 600 mg"))[0]

    assert isinstance(finding, DoacInducerRisk)
    assert finding.agent == "apixaban"
    assert finding.partner_agent == "rifampin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "thromb" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in [
        "apixaban",
        "eliquis",
        "rivaroxaban",
        "xarelto",
        "edoxaban",
        "savaysa",
        "dabigatran",
        "pradaxa",
    ]:
        finding = DoacInducerChecker().check(_meds(f"{primary_agent} dose", "Rifampin 600 mg"))[0]
        assert finding.agent == primary_agent

    for partner_agent, label, severity in [
        ("rifampin", "Rifampin 600 mg", Severity.CRITICAL),
        ("rifampicin", "Rifampicin 600 mg", Severity.CRITICAL),
        ("carbamazepine", "Carbamazepine 200 mg", Severity.HIGH),
        ("tegretol", "Tegretol 200 mg", Severity.HIGH),
        ("phenytoin", "Phenytoin 100 mg", Severity.HIGH),
        ("dilantin", "Dilantin 100 mg", Severity.HIGH),
        ("st johns wort", "St Johns Wort capsule", Severity.HIGH),
        ("hypericum", "Hypericum extract", Severity.HIGH),
    ]:
        finding = DoacInducerChecker().check(_meds("Apixaban 5 mg", label))[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is severity


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = DoacInducerChecker()
    # Distinct from warfarin checkers and DOAC bleed intensifiers
    for agent in ["Warfarin", "Ibuprofen", "Clopidogrel", "Phenobarbital"]:
        assert checker.check(_meds("Apixaban 5 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = DoacInducerChecker()
    assert checker.check(_meds("Apixabanlike", "Rifampinfree")) == []
    assert len(checker.check(_meds("Eliquis", "Rifampin"))) == 1
    assert len(checker.check(_meds("Xarelto", "St John's Wort"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Carbamazepine 200 mg", "Apixaban 5 mg", "Rifampin 600 mg"]
    forward = DoacInducerChecker().check(_meds(*names))
    reverse = DoacInducerChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert (
        len(
            DoacInducerChecker().check(
                _meds(
                    "Apixaban 5 mg",
                    "Apixaban 2.5 mg",
                    "Rifampin 600 mg",
                    "Rifampin 300 mg",
                )
            )
        )
        == 1
    )


def test_findings_sorted_by_severity_first() -> None:
    findings = DoacInducerChecker().check(
        _meds("Apixaban 5 mg", "Carbamazepine 200 mg", "Rifampin 600 mg")
    )
    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.HIGH]
    assert findings[0].partner_agent == "rifampin"
    assert findings[1].partner_agent == "carbamazepine"


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert DoacInducerChecker().check(_meds("Apixaban and rifampin interaction warning")) == []
    finding = ExportedChecker().check(_meds("Pradaxa", "Dilantin"))[0]
    assert finding.severity is Severity.HIGH

"""Tests for the allopurinol + azathioprine/6-MP toxicity checker."""

from medagent.models import AllopurinolAzathioprineRisk, Medication, Severity
from medagent.safety import AllopurinolAzathioprineChecker as ExportedChecker
from medagent.safety.allopurinol_azathioprine_checker import AllopurinolAzathioprineChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_no_findings_when_either_class_is_absent() -> None:
    checker = AllopurinolAzathioprineChecker()
    assert checker.check(_meds("Allopurinol 300 mg")) == []
    assert checker.check(_meds("Azathioprine 50 mg")) == []
    assert checker.check([]) == []


def test_flags_supported_pair_at_expected_severity() -> None:
    finding = AllopurinolAzathioprineChecker().check(
        _meds("Allopurinol 300 mg", "Azathioprine 50 mg")
    )[0]

    assert isinstance(finding, AllopurinolAzathioprineRisk)
    assert finding.agent == "allopurinol"
    assert finding.partner_agent == "azathioprine"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "xanthine oxidase" in finding.rationale.lower()


def test_all_supported_agents_participate() -> None:
    for primary_agent in ["allopurinol", "zyloprim"]:
        finding = AllopurinolAzathioprineChecker().check(
            _meds(f"{primary_agent} dose", "Azathioprine 50 mg")
        )[0]
        assert finding.agent == primary_agent

    for partner_agent in ["azathioprine", "imuran", "mercaptopurine", "6-mp", "purinethol"]:
        finding = AllopurinolAzathioprineChecker().check(
            _meds("Allopurinol 300 mg", f"{partner_agent} dose")
        )[0]
        assert finding.partner_agent == partner_agent
        assert finding.severity is Severity.CRITICAL


def test_related_but_out_of_scope_agents_do_not_flag() -> None:
    checker = AllopurinolAzathioprineChecker()
    for agent in ["Febuxostat", "Mycophenolate", "Cyclosporine"]:
        assert checker.check(_meds("Allopurinol 300 mg", agent)) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    checker = AllopurinolAzathioprineChecker()
    assert checker.check(_meds("Allopurinollike", "Azathioprinenfree")) == []
    assert len(checker.check(_meds("Zyloprim", "Imuran"))) == 1
    assert len(checker.check(_meds("Allopurinol", "6-MP 50 mg"))) == 1


def test_duplicates_are_deduplicated_and_output_is_deterministic() -> None:
    names = ["Azathioprine 50 mg", "Allopurinol 300 mg", "Imuran 50 mg"]
    forward = AllopurinolAzathioprineChecker().check(_meds(*names))
    reverse = AllopurinolAzathioprineChecker().check(_meds(*reversed(names)))
    assert [(item.agent, item.partner_agent, item.partner_medication) for item in forward] == [
        (item.agent, item.partner_agent, item.partner_medication) for item in reverse
    ]
    assert [item.partner_agent for item in forward] == ["azathioprine", "imuran"]
    assert (
        len(
            AllopurinolAzathioprineChecker().check(
                _meds(
                    "Allopurinol 300 mg",
                    "Allopurinol 300 mg",
                    "Azathioprine 50 mg",
                    "Azathioprine 50 mg",
                )
            )
        )
        == 1
    )


def test_single_entry_is_not_coprescription_and_checker_is_exported() -> None:
    assert (
        AllopurinolAzathioprineChecker().check(
            _meds("Allopurinol and Azathioprine interaction warning")
        )
        == []
    )
    finding = ExportedChecker().check(_meds("Zyloprim", "Imuran"))[0]
    assert finding.severity is Severity.CRITICAL

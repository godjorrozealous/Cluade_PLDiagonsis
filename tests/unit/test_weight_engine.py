"""Tests for src/domain/weight_engine.py — validation, computation, confidence extraction."""

import pytest

from src.core.exceptions import WeightValidationError
from src.core.models import (
    ConfidenceLevel,
    DiagnosisResult,
    DiagnosisSummary,
    ToolOutput,
)
from src.domain.weight_engine import WeightEngine


# ============================================================================
# validate
# ============================================================================


def test_validate_accepts_weights_within_bounds(weight_engine: WeightEngine) -> None:
    """validate() passes for weights inside [0.1, 2.0]."""
    weight_engine.validate({"ToolA": 0.5, "ToolB": 1.5})


def test_validate_rejects_weight_below_min(weight_engine: WeightEngine) -> None:
    """validate() raises WeightValidationError when weight < min_weight."""
    with pytest.raises(WeightValidationError) as exc_info:
        weight_engine.validate({"ToolA": 0.05})
    assert "ToolA" in str(exc_info.value)
    assert "0.05" in str(exc_info.value)


def test_validate_rejects_weight_above_max(weight_engine: WeightEngine) -> None:
    """validate() raises WeightValidationError when weight > max_weight."""
    with pytest.raises(WeightValidationError) as exc_info:
        weight_engine.validate({"ToolA": 2.5})
    assert "ToolA" in str(exc_info.value)
    assert "2.5" in str(exc_info.value)


def test_validate_checks_every_tool(weight_engine: WeightEngine) -> None:
    """validate() fails on the first illegal weight encountered."""
    with pytest.raises(WeightValidationError):
        weight_engine.validate({"ToolA": 1.0, "ToolB": 0.0})


def test_custom_bounds_respected() -> None:
    """WeightEngine respects custom min/max passed to __init__."""
    engine = WeightEngine(min_weight=0.5, max_weight=1.5)
    engine.validate({"ToolA": 0.5, "ToolB": 1.5})
    with pytest.raises(WeightValidationError):
        engine.validate({"ToolA": 0.4})
    with pytest.raises(WeightValidationError):
        engine.validate({"ToolA": 1.6})


# ============================================================================
# compute — basic behavior
# ============================================================================


def test_compute_returns_diagnosis_summary(weight_engine: WeightEngine) -> None:
    """compute() returns a DiagnosisSummary."""
    outputs = {"ToolA": ToolOutput(tool_name="ToolA", structured_data={"confidence": 0.8})}
    result = weight_engine.compute(outputs, {"ToolA": 1.0})
    assert isinstance(result, DiagnosisSummary)


def test_compute_populates_results_list(weight_engine: WeightEngine) -> None:
    """compute() creates one DiagnosisResult per tool output."""
    outputs = {
        "ToolA": ToolOutput(tool_name="ToolA"),
        "ToolB": ToolOutput(tool_name="ToolB"),
    }
    summary = weight_engine.compute(outputs, {"ToolA": 1.0, "ToolB": 1.0})
    assert len(summary.results) == 2
    assert {r.tool_name for r in summary.results} == {"ToolA", "ToolB"}


def test_compute_uses_default_weight_when_missing(weight_engine: WeightEngine) -> None:
    """compute() falls back to 1.0 for tools not present in weights dict."""
    outputs = {"ToolA": ToolOutput(tool_name="ToolA", structured_data={"confidence": 0.6})}
    summary = weight_engine.compute(outputs, {})
    assert summary.weights.get("ToolA", 1.0) == 1.0
    assert summary.weighted_scores["ToolA"] == 0.6


# ============================================================================
# compute — weighted scoring and primary diagnosis
# ============================================================================


def test_compute_selects_highest_weighted_as_primary(weight_engine: WeightEngine) -> None:
    """compute() picks the result with the highest weighted score as primary."""
    outputs = {
        "LowTool": ToolOutput(tool_name="LowTool", structured_data={"confidence": 0.9}),
        "HighTool": ToolOutput(tool_name="HighTool", structured_data={"confidence": 0.5}),
    }
    weights = {"LowTool": 0.5, "HighTool": 2.0}
    summary = weight_engine.compute(outputs, weights)

    assert summary.primary_diagnosis is not None
    assert summary.primary_diagnosis.tool_name == "HighTool"
    assert summary.weighted_scores["LowTool"] == 0.45
    assert summary.weighted_scores["HighTool"] == 1.0


def test_compute_primary_is_none_when_no_results(weight_engine: WeightEngine) -> None:
    """compute() leaves primary_diagnosis as None for empty inputs."""
    summary = weight_engine.compute({}, {})
    assert summary.primary_diagnosis is None
    assert summary.results == []


def test_compute_aggregates_evidence(weight_engine: WeightEngine) -> None:
    """compute() flattens all evidence into all_evidence."""
    outputs = {
        "ToolA": ToolOutput(tool_name="ToolA", raw_text="evidence A"),
        "ToolB": ToolOutput(tool_name="ToolB", raw_text="evidence B"),
    }
    summary = weight_engine.compute(outputs, {"ToolA": 1.0, "ToolB": 1.0})
    assert "evidence A" in summary.all_evidence
    assert "evidence B" in summary.all_evidence


# ============================================================================
# _extract_confidence
# ============================================================================


def test_extract_confidence_from_structured_data(weight_engine: WeightEngine) -> None:
    """_extract_confidence reads 'confidence' key from structured_data."""
    output = ToolOutput(tool_name="T", structured_data={"confidence": 0.85})
    assert weight_engine._extract_confidence(output) == 0.85


def test_extract_confidence_fallback_keys(weight_engine: WeightEngine) -> None:
    """_extract_confidence tries confidence_score, match_score, risk_score in order."""
    assert weight_engine._extract_confidence(
        ToolOutput(tool_name="T", structured_data={"confidence_score": 0.7})
    ) == 0.7
    assert weight_engine._extract_confidence(
        ToolOutput(tool_name="T", structured_data={"match_score": 0.6})
    ) == 0.6
    assert weight_engine._extract_confidence(
        ToolOutput(tool_name="T", structured_data={"risk_score": 0.5})
    ) == 0.5


def test_extract_confidence_defaults_to_half(weight_engine: WeightEngine) -> None:
    """_extract_confidence returns 0.5 when no recognized key exists."""
    output = ToolOutput(tool_name="T", structured_data={"other": 0.9})
    assert weight_engine._extract_confidence(output) == 0.5


def test_extract_confidence_defaults_when_no_structured_data(weight_engine: WeightEngine) -> None:
    """_extract_confidence returns 0.5 when structured_data is None."""
    output = ToolOutput(tool_name="T")
    assert weight_engine._extract_confidence(output) == 0.5


def test_extract_confidence_ignores_non_numeric(weight_engine: WeightEngine) -> None:
    """_extract_confidence skips non-numeric values and continues searching."""
    output = ToolOutput(
        tool_name="T",
        structured_data={"confidence": "high", "match_score": 0.65},
    )
    assert weight_engine._extract_confidence(output) == 0.65


# ============================================================================
# _level_from_confidence
# ============================================================================


def test_level_high_at_seven_and_above(weight_engine: WeightEngine) -> None:
    """_level_from_confidence returns HIGH for confidence >= 0.7."""
    assert weight_engine._level_from_confidence(0.7) == ConfidenceLevel.HIGH
    assert weight_engine._level_from_confidence(1.0) == ConfidenceLevel.HIGH


def test_level_medium_between_four_and_seven(weight_engine: WeightEngine) -> None:
    """_level_from_confidence returns MEDIUM for 0.4 <= confidence < 0.7."""
    assert weight_engine._level_from_confidence(0.4) == ConfidenceLevel.MEDIUM
    assert weight_engine._level_from_confidence(0.69) == ConfidenceLevel.MEDIUM


def test_level_low_below_four(weight_engine: WeightEngine) -> None:
    """_level_from_confidence returns LOW for confidence < 0.4."""
    assert weight_engine._level_from_confidence(0.39) == ConfidenceLevel.LOW
    assert weight_engine._level_from_confidence(0.0) == ConfidenceLevel.LOW


# ============================================================================
# _extract_evidence
# ============================================================================


def test_extract_evidence_truncates_raw_text(weight_engine: WeightEngine) -> None:
    """_extract_evidence caps raw_text at 200 characters."""
    long_text = "x" * 300
    output = ToolOutput(tool_name="T", raw_text=long_text)
    evidence = weight_engine._extract_evidence(output)
    assert len(evidence[0]) == 200


def test_extract_evidence_includes_structured_pairs(weight_engine: WeightEngine) -> None:
    """_extract_evidence flattens structured_data key-value pairs."""
    output = ToolOutput(tool_name="T", structured_data={"a": 1, "b": 2})
    evidence = weight_engine._extract_evidence(output)
    assert "a: 1" in evidence
    assert "b: 2" in evidence


def test_extract_evidence_combines_both_sources(weight_engine: WeightEngine) -> None:
    """_extract_evidence merges raw_text and structured_data entries."""
    output = ToolOutput(tool_name="T", raw_text="raw", structured_data={"k": "v"})
    evidence = weight_engine._extract_evidence(output)
    assert evidence[0] == "raw"
    assert "k: v" in evidence

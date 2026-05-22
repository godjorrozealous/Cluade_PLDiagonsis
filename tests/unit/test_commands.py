"""Tests for src/application/commands/*.py — Command classes with mocked dependencies."""

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.exceptions import InvalidStateError, ToolNotFoundError, WeightValidationError
from src.core.models import (
    ConfidenceLevel,
    DiagnosisContext,
    DiagnosisResult,
    DiagnosisSession,
    DiagnosisSummary,
    EventType,
    ExecutionContext,
    FaultContext,
    Intent,
    IntentType,
    SessionStatus,
    ToolOutput,
    UserAction,
)
from src.application.commands.adjust_weight import AdjustWeightCommand, WEIGHT_MIN, WEIGHT_MAX
from src.application.commands.diagnose import DiagnoseCommand
from src.application.commands.exclude import ExcludeToolCommand
from src.application.commands.include_tool import IncludeToolCommand
from src.application.commands.recheck import RecheckToolCommand
from src.application.commands.save_strategy import SaveStrategyCommand


# ============================================================================
# Helpers
# ============================================================================


def _make_context(
    session: DiagnosisSession,
    message: str = "test message",
    intent: Intent | None = None,
) -> ExecutionContext:
    """Build an ExecutionContext for command tests."""
    diagnosis_ctx = DiagnosisContext(
        session_id=session.session_id,
        line_name=session.line_name,
        weights=session.active_weights.copy(),
        excluded_tools=session.excluded_tools.copy(),
        rechecked_tools=session.rechecked_tools.copy(),
    )
    return ExecutionContext(
        session=session,
        diagnosis_ctx=diagnosis_ctx,
        user_message=message,
        intent=intent,
    )


# ============================================================================
# AdjustWeightCommand
# ============================================================================


@pytest.fixture
def adjust_command() -> AdjustWeightCommand:
    """Return an AdjustWeightCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return AdjustWeightCommand(mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_adjust_weight_success(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "1.5"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in adjust_command.execute(ctx)]

    assert len(events) == 2
    assert events[0].event_type == EventType.THINKING
    assert events[1].event_type == EventType.COMPLETE
    adjust_command.session_manager.update_weights.assert_called_once_with("s1", {"ToolA": 1.5})
    assert len(session.action_log) == 1
    assert session.action_log[0].action_type == "adjust_weight"
    assert session.action_log[0].parameters["tool_name"] == "ToolA"
    assert session.action_log[0].parameters["weight"] == 1.5


@pytest.mark.asyncio
async def test_adjust_weight_invalid_missing_tool_name(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError when tool_name is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"weight": "1.5"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "tool_name" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_invalid_missing_weight(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError when weight is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "weight" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_invalid_weight_value(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError for non-numeric weight."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "abc"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "无效" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_out_of_range(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises WeightValidationError when weight is out of range."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "5.0"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(WeightValidationError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "超出范围" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_invalid_state(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError when state machine rejects."""
    adjust_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "1.5"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in adjust_command.execute(ctx)]


# ============================================================================
# ExcludeToolCommand
# ============================================================================


@pytest.fixture
def exclude_command() -> ExcludeToolCommand:
    """Return an ExcludeToolCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return ExcludeToolCommand(mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_exclude_tool_success(exclude_command: ExcludeToolCommand) -> None:
    """exclude_tool executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.EXCLUDE_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in exclude_command.execute(ctx)]

    assert len(events) == 2
    assert events[0].event_type == EventType.THINKING
    assert events[1].event_type == EventType.COMPLETE
    exclude_command.session_manager.exclude_tools.assert_called_once_with("s1", ["ToolA"])
    # When already in MODIFYING, no transition is triggered
    exclude_command.session_manager.transition.assert_not_called()
    assert len(session.action_log) == 1
    assert session.action_log[0].action_type == "exclude"
    assert session.action_log[0].parameters["tool_name"] == "ToolA"


@pytest.mark.asyncio
async def test_exclude_tool_missing_name(exclude_command: ExcludeToolCommand) -> None:
    """exclude_tool raises InvalidStateError when tool_name is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.EXCLUDE_TOOL,
        confidence=0.9,
        parameters={},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in exclude_command.execute(ctx)]

    assert "tool_name" in str(exc_info.value)


@pytest.mark.asyncio
async def test_exclude_tool_invalid_state(exclude_command: ExcludeToolCommand) -> None:
    """exclude_tool raises InvalidStateError when state machine rejects."""
    exclude_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.EXCLUDE_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in exclude_command.execute(ctx)]




# ============================================================================
# IncludeToolCommand
# ============================================================================


@pytest.fixture
def include_command() -> IncludeToolCommand:
    """Return an IncludeToolCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return IncludeToolCommand(mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_include_tool_success(include_command: IncludeToolCommand) -> None:
    """include_tool executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    session.excluded_tools = ["ToolA"]
    intent = Intent(
        intent_type=IntentType.INCLUDE_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in include_command.execute(ctx)]

    assert len(events) == 2
    assert events[0].event_type == EventType.THINKING
    assert events[1].event_type == EventType.COMPLETE
    include_command.session_manager.include_tools.assert_called_once_with("s1", ["ToolA"])
    assert len(session.action_log) == 1
    assert session.action_log[0].action_type == "include"
    assert session.action_log[0].parameters["tool_name"] == "ToolA"
# ============================================================================
# SaveStrategyCommand
# ============================================================================


@pytest.fixture
def save_strategy_command(tmp_path: Path) -> SaveStrategyCommand:
    """Return a SaveStrategyCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return SaveStrategyCommand(
        mock_session_manager,
        mock_state_machine,
        strategies_dir=tmp_path / "strategies",
    )


@pytest.mark.asyncio
async def test_save_strategy_success(save_strategy_command: SaveStrategyCommand) -> None:
    """save_strategy persists strategy to file and returns payload."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    session.active_weights = {"ToolA": 1.0}
    session.excluded_tools = ["ToolB"]
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={"strategy_name": "my_strategy"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in save_strategy_command.execute(ctx)]

    assert len(events) == 2
    assert events[-1].event_type == EventType.COMPLETE
    payload = events[-1].payload
    assert payload["strategy_name"] == "my_strategy"
    assert payload["tool_weights"] == {"ToolA": 1.0}
    assert payload["excluded_tools"] == ["ToolB"]

    # Verify file was written
    strategy_file = save_strategy_command.strategies_dir / "my_strategy.json"
    assert strategy_file.exists()


@pytest.mark.asyncio
async def test_save_strategy_auto_name(save_strategy_command: SaveStrategyCommand) -> None:
    """save_strategy generates a name when strategy_name is not provided."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in save_strategy_command.execute(ctx)]

    payload = events[-1].payload
    assert payload["strategy_name"].startswith("strategy_")


@pytest.mark.asyncio
async def test_save_strategy_invalid_state(save_strategy_command: SaveStrategyCommand) -> None:
    """save_strategy raises InvalidStateError when state machine rejects."""
    save_strategy_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={"strategy_name": "test"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in save_strategy_command.execute(ctx)]


# ============================================================================
# DiagnoseCommand
# ============================================================================


@pytest.fixture
def diagnose_command() -> DiagnoseCommand:
    """Return a DiagnoseCommand with mocked dependencies."""
    mock_registry = MagicMock()
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_event_bus = MagicMock()
    mock_skill_loader = MagicMock()
    mock_prompt_builder = MagicMock()
    mock_diagnosis_planner = AsyncMock()
    mock_tool_executor = AsyncMock()
    mock_report_composer = AsyncMock()

    mock_state_machine.can_execute.return_value = True
    mock_registry.list_tools.return_value = []
    mock_skill_loader.load.return_value = ("# skill", {})
    mock_prompt_builder.build.return_value = "prompt"
    mock_diagnosis_planner.plan.return_value = {
        "tools_to_call": [{"name": "ToolA", "rationale": "test", "parallel": True}],
        "report_structure": ["概述"],
    }
    mock_tool_executor.execute.return_value = {
        "ToolA": ToolOutput(tool_name="ToolA", raw_text="ok"),
    }
    mock_report_composer.compose.return_value = {"report": "# report", "summary": {"fault_type": "雷击", "confidence": 0.85, "primary_tool": "ToolA"}}
    return DiagnoseCommand(
        mock_registry,
        mock_session_manager,
        mock_state_machine,
        mock_event_bus,
        mock_skill_loader,
        mock_prompt_builder,
        mock_diagnosis_planner,
        mock_tool_executor,
        mock_report_composer,
    )


@pytest.mark.asyncio
async def test_diagnose_success(diagnose_command: DiagnoseCommand) -> None:
    """diagnose yields events and completes with report."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    ctx = _make_context(session)

    events = [e async for e in diagnose_command.execute(ctx)]

    assert events[0].event_type == EventType.START
    assert any(e.event_type == EventType.THINKING for e in events)
    assert events[-1].event_type == EventType.COMPLETE
    diagnose_command.session_manager.add_summary.assert_called_once()
    diagnose_command.session_manager.transition.assert_called_with("s1", SessionStatus.MODIFYING)


@pytest.mark.asyncio
async def test_diagnose_invalid_state(diagnose_command: DiagnoseCommand) -> None:
    """diagnose raises InvalidStateError when state machine rejects."""
    diagnose_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.COMPLETED)
    ctx = _make_context(session)

    with pytest.raises(InvalidStateError):
        [e async for e in diagnose_command.execute(ctx)]


# ============================================================================
# RecheckToolCommand
# ============================================================================


@pytest.fixture
def recheck_command() -> RecheckToolCommand:
    """Return a RecheckToolCommand with mocked dependencies."""
    mock_registry = MagicMock()
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    mock_registry.list_tool_names.return_value = ["ToolA"]
    mock_registry.execute_tool = AsyncMock(return_value=ToolOutput(tool_name="ToolA", raw_text="rechecked"))
    return RecheckToolCommand(mock_registry, mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_recheck_tool_success(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in recheck_command.execute(ctx)]

    assert events[0].event_type == EventType.START
    assert any(e.event_type == EventType.RESULT for e in events)
    assert events[-1].event_type == EventType.COMPLETE
    recheck_command.session_manager.add_rechecked.assert_called_once_with("s1", "ToolA")


@pytest.mark.asyncio
async def test_recheck_tool_missing_name(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool raises InvalidStateError when tool_name is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in recheck_command.execute(ctx)]

    assert "tool_name" in str(exc_info.value)


@pytest.mark.asyncio
async def test_recheck_tool_not_found(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool raises ToolNotFoundError for unregistered tools."""
    recheck_command.tool_registry.list_tool_names.return_value = ["OtherTool"]
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={"tool_name": "MissingTool"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(ToolNotFoundError) as exc_info:
        [e async for e in recheck_command.execute(ctx)]

    assert "MissingTool" in str(exc_info.value)


@pytest.mark.asyncio
async def test_recheck_tool_invalid_state(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool raises InvalidStateError when state machine rejects."""
    recheck_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in recheck_command.execute(ctx)]

"""Tests for src/application/commands/save_skill.py — SaveSkillCommand."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.models import (
    DiagnosisSession,
    ExecutionContext,
    DiagnosisContext,
    Intent,
    IntentType,
    SessionStatus,
    EventType,
)
from src.core.exceptions import InvalidStateError
from src.application.commands.save_skill import SaveSkillCommand


# ============================================================================
# Helpers
# ============================================================================


def _make_context(
    session: DiagnosisSession,
    message: str = "test message",
    intent: Intent | None = None,
) -> ExecutionContext:
    """Build an ExecutionContext for save_skill tests."""
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


@pytest.fixture
def save_skill_command(tmp_path: Path) -> SaveSkillCommand:
    """Return a SaveSkillCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return SaveSkillCommand(
        mock_session_manager,
        mock_state_machine,
        skills_dir=tmp_path / "skills",
    )


# ============================================================================
# _build_skill_md
# ============================================================================


def test_save_skill_generates_markdown(save_skill_command: SaveSkillCommand) -> None:
    """_build_skill_md generates correct markdown with tools table."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        status=SessionStatus.MODIFYING,
    )
    session.active_weights = {
        "LightningDiagnosisTool": 1.0,
        "IcingDiagnosisTool": 0.9,
        "WindDiagnosisTool": 0.8,
    }
    session.excluded_tools = ["BirdDamageDiagnosisTool"]
    session.included_tools = ["ManualCheckTool"]

    md = save_skill_command._build_skill_md(session, "my_skill")

    # Name is in the markdown
    assert "# my_skill" in md

    # Included tool (not in active_weights) is present with weight 1.0
    assert "ManualCheckTool" in md
    assert "| ManualCheckTool | 1.0 | 用户动态加入 |" in md

    # Active weight tool is present
    assert "LightningDiagnosisTool" in md
    assert "| LightningDiagnosisTool | 1.0 | 始终启用 |" in md

    # Excluded tool is NOT present in the tools table
    # (It should only appear in the "## 排除的工具" section)
    table_start = md.find("| 工具 | 权重 | 条件 |")
    table_end = md.find("\n\n## 诊断流程")
    table_section = md[table_start:table_end]
    assert "BirdDamageDiagnosisTool" not in table_section

    # Table format is correct
    assert "| 工具 | 权重 | 条件 |" in md
    assert "|------|------|------|" in md

    # Sections exist
    assert "## 描述" in md
    assert "## 推荐工具配置" in md
    assert "## 诊断流程" in md
    assert "## 报告结构" in md
    assert "## 排除的工具" in md

    # Session info in description
    assert "s1" in md
    assert "京西线" in md


# ============================================================================
# execute
# ============================================================================


@pytest.mark.asyncio
async def test_save_skill_success(save_skill_command: SaveSkillCommand) -> None:
    """save_skill persists markdown to file and returns payload."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        status=SessionStatus.MODIFYING,
    )
    session.active_weights = {"ToolA": 1.0}
    session.excluded_tools = ["ToolB"]
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={"skill_name": "my_skill"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in save_skill_command.execute(ctx)]

    assert len(events) == 2
    assert events[0].event_type == EventType.THINKING
    assert events[1].event_type == EventType.COMPLETE
    payload = events[1].payload
    assert payload["skill_name"] == "my_skill"
    assert payload["tool_weights"] == {"ToolA": 1.0}
    assert payload["excluded_tools"] == ["ToolB"]

    # Verify file was written
    skill_file = save_skill_command.skills_dir / "my_skill.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    assert "# my_skill" in content


@pytest.mark.asyncio
async def test_save_skill_auto_name(save_skill_command: SaveSkillCommand) -> None:
    """save_skill generates a name when skill_name is not provided."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        status=SessionStatus.MODIFYING,
    )
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in save_skill_command.execute(ctx)]

    payload = events[1].payload
    assert payload["skill_name"].startswith("skill_")


@pytest.mark.asyncio
async def test_save_skill_invalid_state(save_skill_command: SaveSkillCommand) -> None:
    """save_skill raises InvalidStateError when state machine rejects."""
    save_skill_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        status=SessionStatus.PENDING,
    )
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={"skill_name": "test"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in save_skill_command.execute(ctx)]

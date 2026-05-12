"""Tests for src/domain/report_composer.py — single-shot LLM report generation."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.core.models import ChapterConfig, RenderMode, TemplateConfig, ToolOutput
from src.domain.report_composer import DEFAULT_CHAPTERS, ReportComposer


@pytest.fixture
def report_composer() -> ReportComposer:
    """Return a ReportComposer with a mocked LLMService."""
    mock_llm = AsyncMock()
    return ReportComposer(mock_llm)


@pytest.fixture
def sample_tool_outputs() -> dict[str, ToolOutput]:
    """Return a dict of ToolOutput samples."""
    return {
        "LightningDiagnosisTool": ToolOutput(
            tool_name="LightningDiagnosisTool",
            raw_text="检测到雷击，距离 1.2km",
            structured_data={"distance": 1.2, "intensity": "high"},
        ),
        "WindDiagnosisTool": ToolOutput(
            tool_name="WindDiagnosisTool",
            raw_text="大风天气，风速 25m/s",
            structured_data={"speed": 25.0},
        ),
    }


@pytest.fixture
def sample_template() -> TemplateConfig:
    """Return a TemplateConfig with custom chapters."""
    return TemplateConfig(
        name="custom",
        chapters=[
            ChapterConfig(
                chapter_type="overview",
                title="概述",
                required=True,
                render_mode=RenderMode.TEXT,
            ),
            ChapterConfig(
                chapter_type="conclusion",
                title="诊断结论",
                required=True,
                render_mode=RenderMode.TEXT,
            ),
        ],
    )


# ============================================================================
# compose
# ============================================================================


@pytest.mark.asyncio
async def test_compose_generates_report(
    report_composer: ReportComposer,
    sample_tool_outputs: dict[str, ToolOutput],
    sample_template: TemplateConfig,
) -> None:
    """compose() calls LLM with prompt containing tool data and returns formatted report."""
    report_composer.llm.chat = AsyncMock(
        return_value="## 概述\n概述内容\n\n## 诊断结论\n结论内容"
    )

    result = await report_composer.compose(
        tool_outputs=sample_tool_outputs,
        template=sample_template,
        session_id="sess-001",
    )

    # 验证输出包含章节和工具数据
    assert "## 概述" in result["report"]
    assert "## 诊断结论" in result["report"]
    assert "# 输电线路故障诊断报告" in result["report"]

    # 验证 LLM 被调用且 prompt 包含工具数据
    report_composer.llm.chat.assert_awaited_once()
    call_messages = report_composer.llm.chat.call_args.args[0]
    assert call_messages[0]["role"] == "system"
    assert "输电线路故障诊断报告撰写专家" in call_messages[0]["content"]
    assert call_messages[1]["role"] == "user"
    prompt = call_messages[1]["content"]
    assert "LightningDiagnosisTool" in prompt
    assert "WindDiagnosisTool" in prompt
    assert "检测到雷击" in prompt
    assert "25.0" in prompt
    assert "概述" in prompt
    assert "诊断结论" in prompt


@pytest.mark.asyncio
async def test_compose_without_template_uses_defaults(
    report_composer: ReportComposer,
    sample_tool_outputs: dict[str, ToolOutput],
) -> None:
    """compose() uses DEFAULT_CHAPTERS when template is None."""
    report_composer.llm.chat = AsyncMock(
        return_value="## 概述\n...\n## 故障分析\n..."
    )

    result = await report_composer.compose(
        tool_outputs=sample_tool_outputs,
        template=None,
        session_id="sess-002",
    )

    # 验证默认章节被使用
    report_composer.llm.chat.assert_awaited_once()
    call_messages = report_composer.llm.chat.call_args.args[0]
    prompt = call_messages[1]["content"]
    for chapter in DEFAULT_CHAPTERS:
        assert chapter in prompt

    # 验证返回结果
    assert "# 输电线路故障诊断报告" in result["report"]

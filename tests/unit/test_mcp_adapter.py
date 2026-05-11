"""Tests for src/infrastructure/adapters/mcp_adapter.py — mock execution and normalization."""

import pytest

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.adapters.mcp_adapter import MCPToolAdapter


# ============================================================================
# Properties
# ============================================================================


def test_mcp_adapter_properties_reflect_config() -> None:
    """MCPToolAdapter exposes config values through its properties."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "display_name": "Lightning",
        "description": "Detects lightning",
        "category": "electrical",
    })

    assert adapter.name == "LightningDiagnosisTool"
    assert adapter.display_name == "Lightning"
    assert adapter.description == "Detects lightning"
    assert adapter.category == "electrical"


def test_mcp_adapter_defaults_when_config_sparse() -> None:
    """MCPToolAdapter fills sensible defaults for missing config keys."""
    adapter = MCPToolAdapter({})

    assert adapter.name == "unknown"
    assert adapter.display_name == "unknown"
    assert adapter.description == ""
    assert adapter.category == "unknown"


# ============================================================================
# execute — mocked outputs
# ============================================================================


@pytest.mark.asyncio
async def test_execute_returns_tool_output() -> None:
    """execute() returns a ToolOutput with structured data."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "display_name": "Lightning",
    })
    context = FaultContext(line_id="L1", line_name="LineA")

    output = await adapter.execute(context)

    assert isinstance(output, ToolOutput)
    assert output.tool_name == "LightningDiagnosisTool"
    assert output.structured_data is not None
    assert "longitude" in output.structured_data


@pytest.mark.asyncio
async def test_execute_returns_unknown_tool_data() -> None:
    """execute() returns generic data for unrecognized tool names."""
    adapter = MCPToolAdapter({
        "tool_name": "UnknownTool",
        "display_name": "Unknown",
    })
    context = FaultContext(line_id="L1", line_name="LineA")

    output = await adapter.execute(context)

    assert output.structured_data == {"result": "暂无数据"}


@pytest.mark.asyncio
async def test_execute_includes_raw_text() -> None:
    """execute() populates raw_text with a human-readable summary."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "display_name": "Lightning",
    })
    context = FaultContext(line_id="L1", line_name="LineA")

    output = await adapter.execute(context)

    assert output.raw_text is not None
    assert "Lightning" in output.raw_text


@pytest.mark.asyncio
async def test_execute_includes_metadata() -> None:
    """execute() tags output with source and server metadata."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "mcp_server": "http://localhost:8000",
    })
    context = FaultContext(line_id="L1", line_name="LineA")

    output = await adapter.execute(context)

    assert output.metadata.get("source") == "mcp"
    assert output.metadata.get("server") == "http://localhost:8000"


# ============================================================================
# _normalize_output
# ============================================================================


@pytest.mark.asyncio
async def test_normalize_output_with_empty_dict() -> None:
    """_normalize_output handles empty dict gracefully."""
    adapter = MCPToolAdapter({"tool_name": "T"})
    output = adapter._normalize_output({})

    assert output.tool_name == "T"
    assert output.raw_text == "{}"


@pytest.mark.asyncio
async def test_normalize_output_with_non_dict() -> None:
    """_normalize_output stringifies non-dict results."""
    adapter = MCPToolAdapter({"tool_name": "T"})
    output = adapter._normalize_output("plain text")

    assert output.raw_text == "plain text"

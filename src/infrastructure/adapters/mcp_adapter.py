"""MCP 工具适配器 — HTTP 客户端模式"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.adapters.base import ToolAdapter

logger = logging.getLogger(__name__)


class MCPToolAdapter(ToolAdapter):
    """MCP 工具适配器 — 通过 HTTP 调用独立 MCP 服务"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._name = config.get("tool_name", "unknown")
        self._display_name = config.get("display_name", self._name)
        self._description = config.get("description", "")
        self._category = config.get("category", "unknown")
        self.url = config.get("url", "")
        self.timeout = config.get("timeout", 30)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> str:
        return self._category

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def execute(self, context: FaultContext) -> ToolOutput:
        """调用 MCP 服务"""
        client = await self._get_client()
        payload = {
            "line_name": context.line_name,
            "voltage_level": None,
            "fault_time": context.fault_time.isoformat() if context.fault_time else None,
            "additional_info": {
                "line_id": context.line_id,
                "tower_id": context.tower_id,
                "weather_info": context.weather_info,
                "scada_data": context.scada_data,
                "wave_data": context.wave_data,
                "images": context.images,
                **context.additional_info,
            },
        }

        try:
            response = await client.post(
                f"{self.url}/diagnose",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return ToolOutput(
                tool_name=self.name,
                raw_text=data.get("raw_text", ""),
                structured_data=data.get("structured_data", {}),
                metadata=data.get("metadata", {}),
            )
        except httpx.HTTPError as e:
            logger.error(f"MCP 服务调用失败 {self.name}: {e}")
            return ToolOutput(
                tool_name=self.name,
                raw_text=f"工具调用失败: {e}",
                structured_data={"error": str(e), "fault_type": "未知", "confidence": 0.0},
                metadata={"error": True},
            )
        except Exception as e:
            logger.error(f"MCP 服务未知错误 {self.name}: {e}")
            return ToolOutput(
                tool_name=self.name,
                raw_text=f"工具调用失败: {e}",
                structured_data={"error": str(e), "fault_type": "未知", "confidence": 0.0},
                metadata={"error": True},
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

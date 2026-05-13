"""MCP 工具适配器

支持模拟模式（开发阶段）和真实 HTTP MCP 客户端（生产阶段）。
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.models import FaultContext, ToolOutput
from src.core.exceptions import MCPConnectionError, ToolExecutionError
from src.infrastructure.adapters.base import ToolAdapter

logger = logging.getLogger(__name__)


class HTTPMCPClient:
    """HTTP MCP 客户端

    通过 JSON-RPC over HTTP 调用远程 MCP 服务器上的工具。
    """

    def __init__(self, server_url: str, timeout: float = 30.0):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._initialized = False
        self._client = None

    async def _get_client(self):
        """惰性初始化 httpx 客户端"""
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def initialize(self) -> None:
        """初始化 MCP 连接（发送 initialize 请求）"""
        if self._initialized:
            return

        client = await self._get_client()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pldiagnosis", "version": "0.2.0"},
            },
        }

        try:
            response = await client.post(
                f"{self.server_url}/mcp",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            self._initialized = True
            logger.info(f"MCP 服务器初始化成功: {self.server_url}")
        except Exception as e:
            raise MCPConnectionError(
                f"MCP 服务器初始化失败: {e}",
                details={"server_url": self.server_url},
            )

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用远程工具"""
        await self.initialize()

        client = await self._get_client()

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        try:
            response = await client.post(
                f"{self.server_url}/mcp",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise ToolExecutionError(
                    f"工具执行错误: {data['error'].get('message', '未知错误')}",
                    details={"tool": tool_name, "error": data["error"]},
                )

            return data.get("result", {})
        except ToolExecutionError:
            raise
        except Exception as e:
            raise MCPConnectionError(
                f"MCP 调用失败: {e}",
                details={"tool": tool_name, "server_url": self.server_url},
            )

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False


class MCPToolAdapter(ToolAdapter):
    """MCP 工具适配器

    通过 MCP 协议调用远程诊断工具。
    支持模拟模式和真实 HTTP MCP 客户端模式。
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._name = config.get("tool_name", "unknown")
        self._display_name = config.get("display_name", self._name)
        self._description = config.get("description", "")
        self._category = config.get("category", "unknown")
        self._mcp_server = config.get("mcp_server", "")
        self._mcp_server_url = config.get("mcp_server_url", "")
        self._use_mock = not bool(self._mcp_server_url)
        self._http_client: Optional[HTTPMCPClient] = None

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

    async def execute(self, context: FaultContext) -> ToolOutput:
        """调用 MCP 工具"""
        try:
            if self._use_mock:
                result = await self._mock_call(context)
            else:
                result = await self._http_call(context)
            return self._normalize_output(result)
        except Exception as e:
            if isinstance(e, (MCPConnectionError, ToolExecutionError)):
                raise
            raise ToolExecutionError(
                f"工具 {self.name} 执行失败: {str(e)}",
                details={"tool": self.name, "error": str(e)},
            )

    async def _http_call(self, context: FaultContext) -> dict:
        """通过 HTTP MCP 客户端调用远程工具"""
        if self._http_client is None:
            self._http_client = HTTPMCPClient(self._mcp_server_url)

        arguments = {
            "line_name": context.line_name,
            "line_id": context.line_id,
            "tower_id": context.tower_id,
            "fault_time": context.fault_time.isoformat() if context.fault_time else None,
            "weather_info": context.weather_info,
            "scada_data": context.scada_data,
            "wave_data": context.wave_data,
            "additional_info": context.additional_info,
        }

        result = await self._http_client.call_tool(self._name, arguments)

        # MCP 返回格式: {"content": [...], "isError": false}
        if "content" in result:
            content_items = result["content"]
            for item in content_items:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        # 尝试解析为 JSON
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"result": text}
            return {"result": str(content_items)}

        return result

    async def _mock_call(self, context: FaultContext) -> dict:
        """模拟 MCP 调用（开发阶段）"""
        # 根据工具类型返回不同的模拟数据
        mock_data = {
            "LightningDiagnosisTool": {
                "strike_time": datetime.now().isoformat(),
                "longitude": 114.3055,
                "latitude": 30.5928,
                "current": 45.2,
                "distance_to_line": 1.2,
                "fault_type": "雷击故障",
                "confidence": 0.85,
            },
            "IcingDiagnosisTool": {
                "temperature": -2.5,
                "humidity": 85.0,
                "wind_speed": 8.5,
                "icing_thickness": 5.2,
                "icing_risk_level": "高",
                "fault_type": "覆冰故障",
                "confidence": 0.72,
            },
            "WindDiagnosisTool": {
                "max_wind_speed": 22.5,
                "wind_direction": "西北",
                "gust_speed": 28.0,
                "deflection_risk": "中",
                "fault_type": "风偏故障",
                "confidence": 0.60,
            },
            "BirdDamageDiagnosisTool": {
                "bird_species_count": 12,
                "activity_level": "高",
                "nesting_sites": 3,
                "damage_history": "2024年3月曾发生鸟害导致的跳闸",
                "fault_type": "鸟害故障",
                "confidence": 0.55,
            },
        }
        return mock_data.get(self.name, {"result": "暂无数据"})

    def _normalize_output(self, result: dict) -> ToolOutput:
        """标准化输出为 ToolOutput"""
        # 判断是否为结构化数据
        if isinstance(result, dict) and len(result) > 0:
            return ToolOutput(
                tool_name=self.name,
                structured_data=result,
                raw_text=self._structured_to_text(result),
                metadata={"source": "mcp", "server": self._mcp_server},
            )
        return ToolOutput(
            tool_name=self.name,
            raw_text=str(result),
            metadata={"source": "mcp", "server": self._mcp_server},
        )

    def _structured_to_text(self, data: dict) -> str:
        """将结构化数据转换为自然语言描述"""
        lines = [f"{self.display_name}诊断结果："]
        for key, value in data.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

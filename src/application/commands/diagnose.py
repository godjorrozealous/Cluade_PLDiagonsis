"""诊断 Command"""

import logging
from typing import AsyncIterator

from src.core.models import (
    DiagnosisContext,
    DiagnosisSession,
    Event,
    ExecutionContext,
    FaultContext,
    SessionStatus,
)
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.infrastructure.adapters.registry import ToolRegistry
from src.infrastructure.event_bus import EventBus
from src.domain.report_engine import ReportEngine
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.weight_engine import WeightEngine

logger = logging.getLogger(__name__)


class DiagnoseCommand(Command):
    """诊断 Command"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        weight_engine: WeightEngine,
        report_engine: ReportEngine,
        session_manager: SessionManager,
        state_machine: StateMachine,
        event_bus: EventBus,
    ):
        self.tool_registry = tool_registry
        self.weight_engine = weight_engine
        self.report_engine = report_engine
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.event_bus = event_bus

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行诊断"""
        session = ctx.session

        # 1. 验证状态
        if not self.state_machine.can_execute(session, "diagnose"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许执行诊断"
            )

        yield Event.start(session.session_id, "开始故障诊断...")

        # 2. 解析故障上下文
        fault_context = self._parse_fault_context(ctx.user_message, session)
        yield Event.thinking(session.session_id, f"解析线路信息: {fault_context.line_name}")

        # 3. 转换状态
        self.session_manager.transition(session.session_id, SessionStatus.DIAGNOSING)

        # 4. 获取可用工具（排除 excluded_tools）
        all_tools = self.tool_registry.list_tool_names()
        available_tools = [
            t for t in all_tools if t not in ctx.diagnosis_ctx.excluded_tools
        ]
        yield Event.thinking(
            session.session_id,
            f"调用诊断工具: {', '.join(available_tools)}",
        )

        # 5. 并行执行工具
        tool_outputs = await self.tool_registry.execute_parallel(
            available_tools, fault_context
        )
        yield Event.result(session.session_id, {"tool_count": len(tool_outputs)})

        # 6. 加权分析
        yield Event.thinking(session.session_id, "综合加权分析中...")
        weights = ctx.diagnosis_ctx.weights or session.active_weights
        summary = self.weight_engine.compute(tool_outputs, weights)

        # 7. 生成报告（ReportEngine 会自动使用默认章节）
        yield Event.thinking(session.session_id, "生成诊断报告...")
        from src.core.models import TemplateConfig
        template = TemplateConfig(name="default")
        report = await self.report_engine.generate(
            summary, template, tool_outputs, session.session_id
        )

        # 8. 保存结果
        summary.fault_context = fault_context
        self.session_manager.add_summary(session.session_id, summary)
        self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)

        yield Event.complete(
            session.session_id,
            {
                "report": report,
                "primary_diagnosis": summary.primary_diagnosis.fault_type
                if summary.primary_diagnosis
                else "未知",
                "confidence": summary.primary_diagnosis.confidence
                if summary.primary_diagnosis
                else 0,
            },
        )

    def _parse_fault_context(self, message: str, session: DiagnosisSession) -> FaultContext:
        """解析故障上下文"""
        from src.infrastructure.fault_parser import FaultContextParser

        fault_ctx = FaultContextParser.parse(message, session.line_name)
        fault_ctx.line_id = session.session_id
        return fault_ctx

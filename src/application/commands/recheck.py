"""重新检查工具 Command"""

import logging
from typing import AsyncIterator

from src.core.models import (
    DiagnosisSummary,
    Event,
    ExecutionContext,
    FaultContext,
    SessionStatus,
)
from src.core.exceptions import InvalidStateError, ToolNotFoundError
from src.application.commands.base import Command
from src.infrastructure.adapters.registry import ToolRegistry
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.weight_engine import WeightEngine

logger = logging.getLogger(__name__)


class RecheckToolCommand(Command):
    """重新检查工具 Command

    对指定工具重新执行诊断，更新 rechecked_tools 列表，
    获取新结果后更新 current_summary。
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        weight_engine: WeightEngine,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.tool_registry = tool_registry
        self.weight_engine = weight_engine
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行重新检查操作"""
        session = ctx.session
        tool_name = self._extract_tool_name(ctx)

        yield Event.start(session.session_id, f"重新检查工具: {tool_name}...")

        self._validate_state(session)
        self._validate_tool(tool_name)

        # 清除该工具缓存，强制重新调用
        if tool_name in session.tool_outputs_cache:
            del session.tool_outputs_cache[tool_name]
            logger.info(f"清除缓存: {tool_name}")

        self.session_manager.transition(session.session_id, SessionStatus.RECHECKING)
        yield Event.status(
            session.session_id,
            {"status": SessionStatus.RECHECKING.value},
        )

        fault_context = self._build_fault_context(session)
        yield Event.thinking(session.session_id, f"重新执行 {tool_name}...")

        tool_output = await self.tool_registry.execute_tool(tool_name, fault_context)
        yield Event.result(
            session.session_id,
            {"tool_name": tool_name, "output": tool_output.raw_text},
        )

        self.session_manager.add_rechecked(session.session_id, tool_name)

        updated_summary = self._recompute_summary(ctx, tool_name, tool_output)
        self.session_manager.add_summary(session.session_id, updated_summary)

        self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)
        yield Event.status(
            session.session_id,
            {"status": SessionStatus.MODIFYING.value},
        )

        logger.info(f"重新检查完成: {session.session_id} -> {tool_name}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已重新检查 {tool_name}",
                "rechecked_tools": session.rechecked_tools,
                "primary_diagnosis": updated_summary.primary_diagnosis.fault_type
                if updated_summary.primary_diagnosis
                else "未知",
            },
        )

    def _extract_tool_name(self, ctx: ExecutionContext) -> str:
        """从意图参数中提取工具名"""
        if ctx.intent:
            tool_name = ctx.intent.parameters.get("tool_name", "")
            if tool_name:
                return tool_name
        raise InvalidStateError("缺少 tool_name 参数")

    def _validate_state(self, session) -> None:
        """验证当前状态是否允许重新检查"""
        if not self.state_machine.can_execute(session, "recheck"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许重新检查"
            )

    def _validate_tool(self, tool_name: str) -> None:
        """验证工具是否已注册"""
        if tool_name not in self.tool_registry.list_tool_names():
            raise ToolNotFoundError(f"工具不存在: {tool_name}")

    def _build_fault_context(self, session) -> FaultContext:
        """构建故障上下文"""
        current = session.current_summary
        if current and current.fault_context:
            return current.fault_context
        return FaultContext(
            line_id=session.session_id,
            line_name=session.line_name,
        )

    def _recompute_summary(
        self, ctx: ExecutionContext, tool_name: str, new_output
    ) -> DiagnosisSummary:
        """重新计算诊断摘要"""
        current = ctx.session.current_summary
        if not current:
            return self._compute_from_single(tool_name, new_output, ctx)

        tool_outputs = self._gather_outputs(current, tool_name, new_output)
        weights = getattr(ctx.diagnosis_ctx, 'weights', None) or ctx.session.active_weights
        return self.weight_engine.compute(tool_outputs, weights)

    def _gather_outputs(self, current, tool_name, new_output):
        """收集所有工具输出（用新输出替换旧输出）"""
        outputs = {}
        for result in current.results:
            if result.tool_name != tool_name:
                outputs[result.tool_name] = self._result_to_output(result)
        outputs[tool_name] = new_output
        return outputs

    def _result_to_output(self, result):
        """将 DiagnosisResult 转换为 ToolOutput（简化版）"""
        from src.core.models import ToolOutput
        return ToolOutput(
            tool_name=result.tool_name,
            raw_text=result.details.get("raw_text", ""),
            structured_data=result.details,
        )

    def _compute_from_single(self, tool_name, output, ctx):
        """仅基于单个工具输出计算摘要"""
        weights = ctx.diagnosis_ctx.weights or ctx.session.active_weights
        return self.weight_engine.compute({tool_name: output}, weights)

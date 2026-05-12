"""调整权重 Command"""

import logging
from typing import AsyncIterator

from src.core.models import DiagnosisSummary, Event, ExecutionContext, SessionStatus, UserAction
from src.core.exceptions import InvalidStateError, WeightValidationError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.weight_engine import WeightEngine

logger = logging.getLogger(__name__)

WEIGHT_MIN = 0.1
WEIGHT_MAX = 2.0


class AdjustWeightCommand(Command):
    """调整权重 Command

    调整指定工具的权重，验证范围后更新 active_weights，
    如果有 current_summary 则重新加权计算。
    """

    def __init__(
        self,
        weight_engine: WeightEngine,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.weight_engine = weight_engine
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行权重调整操作"""
        session = ctx.session
        tool_name, new_weight = self._extract_params(ctx)

        yield Event.thinking(
            session.session_id,
            f"调整 {tool_name} 权重为 {new_weight}...",
        )

        self._validate_state(session)
        self._validate_weight(tool_name, new_weight)

        self.session_manager.update_weights(
            session.session_id, {tool_name: new_weight}
        )
        session.action_log.append(
            UserAction(
                action_type="adjust_weight",
                parameters={"tool_name": tool_name, "weight": new_weight},
            )
        )

        updated_summary = self._maybe_recompute(session)

        logger.info(f"权重调整完成: {session.session_id} -> {tool_name}={new_weight}")

        payload = {
            "message": f"已调整 {tool_name} 权重为 {new_weight}",
            "active_weights": session.active_weights,
        }
        if updated_summary:
            payload["primary_diagnosis"] = (
                updated_summary.primary_diagnosis.fault_type
                if updated_summary.primary_diagnosis
                else "未知"
            )
            payload["confidence"] = (
                updated_summary.primary_diagnosis.confidence
                if updated_summary.primary_diagnosis
                else 0
            )

        yield Event.complete(session.session_id, payload)

    def _extract_params(self, ctx: ExecutionContext) -> tuple[str, float]:
        """从意图参数中提取工具名和新权重"""
        if not ctx.intent:
            raise InvalidStateError("缺少意图参数")

        tool_name = ctx.intent.parameters.get("tool_name", "")
        weight_raw = ctx.intent.parameters.get("weight")

        if not tool_name:
            raise InvalidStateError("缺少 tool_name 参数")
        if weight_raw is None:
            raise InvalidStateError("缺少 weight 参数")

        try:
            new_weight = float(weight_raw)
        except (ValueError, TypeError) as exc:
            raise InvalidStateError(f"权重值无效: {weight_raw}") from exc

        return tool_name, new_weight

    def _validate_state(self, session) -> None:
        """验证当前状态是否允许调整权重"""
        if not self.state_machine.can_execute(session, "adjust_weight"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许调整权重"
            )

    def _validate_weight(self, tool_name: str, weight: float) -> None:
        """验证权重范围"""
        if weight < WEIGHT_MIN or weight > WEIGHT_MAX:
            raise WeightValidationError(
                f"权重 {tool_name}={weight} 超出范围 [{WEIGHT_MIN}, {WEIGHT_MAX}]"
            )

    def _maybe_recompute(self, session) -> DiagnosisSummary | None:
        """如有 current_summary，则重新加权计算"""
        current = session.current_summary
        if not current:
            return None

        tool_outputs = self._rebuild_outputs(current)
        weights = session.active_weights.copy()
        new_summary = self.weight_engine.compute(tool_outputs, weights)
        self.session_manager.add_summary(session.session_id, new_summary)
        return new_summary

    def _rebuild_outputs(self, current) -> dict:
        """从 current_summary 重建工具输出字典"""
        from src.core.models import ToolOutput

        outputs = {}
        for result in current.results:
            outputs[result.tool_name] = ToolOutput(
                tool_name=result.tool_name,
                raw_text=result.details.get("raw_text", ""),
                structured_data=result.details,
            )
        return outputs

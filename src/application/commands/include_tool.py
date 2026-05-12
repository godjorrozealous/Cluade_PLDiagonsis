"""恢复工具 Command

从会话的排除列表中恢复指定工具。
"""

import logging
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


class IncludeToolCommand(Command):
    """恢复工具 Command

    从会话的 excluded_tools 列表中移除指定工具，
    使该工具在后续诊断中重新生效。
    """

    def __init__(
        self,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行恢复工具操作"""
        session = ctx.session
        tool_name = self._extract_tool_name(ctx)

        yield Event.thinking(session.session_id, f"准备恢复工具: {tool_name}...")

        self._validate_state(session)

        self.session_manager.include_tool(session.session_id, tool_name)

        logger.info(f"已恢复工具: {session.session_id} -> {tool_name}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已恢复工具: {tool_name}",
                "excluded_tools": session.excluded_tools,
                "status": session.status.value,
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
        """验证当前状态是否允许恢复操作"""
        if not self.state_machine.can_execute(session, "include"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许恢复工具"
            )

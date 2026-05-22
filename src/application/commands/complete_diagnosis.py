"""完成诊断 Command

将会话状态标记为 COMPLETED。
"""

import logging
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext, SessionStatus, UserAction
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


class CompleteDiagnosisCommand(Command):
    """完成诊断 Command"""

    def __init__(
        self,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行完成诊断操作"""
        session = ctx.session

        yield Event.thinking(session.session_id, "正在完成诊断...")

        if not self.state_machine.can_execute(session, "complete"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许完成诊断"
            )

        session.action_log.append(
            UserAction(action_type="complete", parameters={})
        )

        self.session_manager.transition(session.session_id, SessionStatus.COMPLETED)
        yield Event.status(
            session.session_id,
            {"status": SessionStatus.COMPLETED.value},
        )

        logger.info(f"诊断完成: {session.session_id}")

        yield Event.complete(
            session.session_id,
            {
                "message": "诊断已完成",
                "status": session.status.value,
                "line_name": session.line_name,
            },
        )

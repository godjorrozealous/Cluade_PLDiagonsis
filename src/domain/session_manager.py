"""会话管理器

管理诊断会话的 CRUD 和生命周期。
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.core.models import (
    DiagnosisSession,
    DiagnosisSummary,
    SessionStatus,
)
from src.core.exceptions import SessionNotFoundError
from src.infrastructure.event_bus import EventBus
from src.infrastructure.line_normalizer import LineNormalizer
from src.infrastructure.session_repository import SessionRepository
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器"""

    def __init__(
        self,
        event_bus: EventBus,
        state_machine: StateMachine,
        repository: Optional[SessionRepository] = None,
    ):
        self.event_bus = event_bus
        self.state_machine = state_machine
        self.repository = repository
        self._default_skill_name: str = "comprehensive_diagnosis"

        if repository is not None:
            self._sessions = repository.load_all()
            self._active_session_id = None
        else:
            self._sessions: Dict[str, DiagnosisSession] = {}
            self._active_session_id = None

    def _persist(self) -> None:
        """持久化当前会话状态"""
        if self.repository is not None:
            try:
                self.repository.save_all(self._sessions)
            except Exception:
                logger.exception("会话持久化失败")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, line_name: str) -> DiagnosisSession:
        """创建新会话"""
        normalized = LineNormalizer.normalize(line_name)
        session = DiagnosisSession(
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            line_name=normalized,
            status=SessionStatus.PENDING,
        )
        session.active_skill_name = self._default_skill_name
        self._sessions[session.session_id] = session
        self._active_session_id = session.session_id

        logger.info(f"创建会话: {session.session_id} ({normalized})")
        self._persist()
        return session

    def get(self, session_id: str) -> DiagnosisSession:
        """获取会话"""
        if session_id not in self._sessions:
            raise SessionNotFoundError(f"会话不存在: {session_id}")
        return self._sessions[session_id]

    def get_active(self) -> Optional[DiagnosisSession]:
        """获取当前活跃会话"""
        if not self._active_session_id:
            return None
        return self._sessions.get(self._active_session_id)

    def get_or_create(self, line_name: str) -> DiagnosisSession:
        """获取或创建会话

        同一线路（标准化后）且处于 pending 状态的会话会被复用。
        已开始诊断的会话不再复用，避免状态冲突。
        """
        normalized = LineNormalizer.normalize(line_name)

        # 查找现有 pending 会话
        for sess in self._sessions.values():
            if (
                LineNormalizer.normalize(sess.line_name) == normalized
                and sess.status == SessionStatus.PENDING
            ):
                self._active_session_id = sess.session_id
                logger.info(f"复用会话: {sess.session_id} ({normalized})")
                return sess

        # 创建新会话
        return self.create(line_name)
    def set_default_skill(self, name: str) -> None:
        """设置全局默认技能"""
        self._default_skill_name = name
        logger.info(f"设置默认技能: {name}")

    def list_sessions(self) -> List[DiagnosisSession]:
        """列出所有会话"""
        return list(self._sessions.values())

    def switch_active(self, session_id: str) -> DiagnosisSession:
        """切换活跃会话"""
        session = self.get(session_id)
        self._active_session_id = session_id
        logger.info(f"切换活跃会话: {session_id}")
        return session

    # ------------------------------------------------------------------
    # 状态管理
    # ------------------------------------------------------------------

    def transition(self, session_id: str, target: SessionStatus) -> None:
        """转换会话状态"""
        session = self.get(session_id)
        self.state_machine.transition(session, target)
        self._persist()

    # ------------------------------------------------------------------
    # 诊断历史
    # ------------------------------------------------------------------

    def add_summary(self, session_id: str, summary: DiagnosisSummary) -> None:
        """添加诊断摘要"""
        session = self.get(session_id)
        session.summaries.append(summary)
        session.current_summary = summary
        session.updated_at = datetime.now()
        self._persist()

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------

    def update_weights(
        self, session_id: str, weights: Dict[str, float]
    ) -> None:
        """更新会话权重"""
        session = self.get(session_id)
        session.active_weights.update(weights)
        session.updated_at = datetime.now()
        self._persist()
        logger.info(f"更新权重: {session_id} -> {weights}")

    def exclude_tool(self, session_id: str, tool_name: str) -> None:
        """排除工具"""
        session = self.get(session_id)
        if tool_name not in session.excluded_tools:
            session.excluded_tools.append(tool_name)
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"排除工具: {session_id} -> {tool_name}")

    def include_tool(self, session_id: str, tool_name: str) -> None:
        """恢复工具"""
        session = self.get(session_id)
        if tool_name in session.excluded_tools:
            session.excluded_tools.remove(tool_name)
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"恢复工具: {session_id} -> {tool_name}")

    def exclude_tools(self, session_id: str, tool_names: List[str]) -> None:
        """批量排除工具"""
        session = self.get(session_id)
        changed = False
        for tool_name in tool_names:
            if tool_name not in session.excluded_tools:
                session.excluded_tools.append(tool_name)
                changed = True
        if changed:
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"批量排除工具: {session_id} -> {tool_names}")

    def include_tools(self, session_id: str, tool_names: List[str]) -> None:
        """批量恢复工具"""
        session = self.get(session_id)
        changed = False
        for tool_name in tool_names:
            if tool_name in session.excluded_tools:
                session.excluded_tools.remove(tool_name)
                changed = True
        if changed:
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"批量恢复工具: {session_id} -> {tool_names}")

    def add_rechecked(self, session_id: str, tool_name: str) -> None:
        """记录重新检查"""
        session = self.get(session_id)
        if tool_name not in session.rechecked_tools:
            session.rechecked_tools.append(tool_name)
            session.updated_at = datetime.now()
            self._persist()

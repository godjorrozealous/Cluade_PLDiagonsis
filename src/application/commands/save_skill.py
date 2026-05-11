"""保存技能 Command

将当前会话的调整保存为 Markdown 技能文件，
包括工具权重、排除工具列表、诊断流程和报告结构，
持久化到 skills/ 目录下的 Markdown 文件。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from src.core.models import DiagnosisSession, Event, ExecutionContext, SessionStatus
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = Path("skills")


class SaveSkillCommand(Command):
    """保存技能 Command

    将当前会话的配置保存为 Markdown 技能文件，
    包括推荐工具配置（权重表）、诊断流程、报告结构等，
    持久化到 skills/ 目录下的 Markdown 文件。
    """

    def __init__(
        self,
        session_manager: SessionManager,
        state_machine: StateMachine,
        skills_dir: Path | None = None,
    ):
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.skills_dir = skills_dir or DEFAULT_SKILLS_DIR

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行保存技能操作

        Args:
            ctx: 执行上下文，包含会话、用户消息和意图

        Yields:
            Event: 执行过程中的事件（thinking、complete）

        Raises:
            InvalidStateError: 当前状态不允许保存技能
        """
        session = ctx.session
        skill_name = self._extract_skill_name(ctx)

        yield Event.thinking(
            session.session_id,
            f"保存技能: {skill_name}...",
        )

        self._validate_state(session)
        self._ensure_skills_dir()

        markdown_content = self._build_skill_md(session, skill_name)
        file_path = self._save_to_file(skill_name, markdown_content)

        session.active_skill_name = skill_name
        self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)

        logger.info(f"技能已保存: {session.session_id} -> {file_path}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"技能 '{skill_name}' 已保存",
                "skill_name": skill_name,
                "file_path": str(file_path),
                "tool_weights": session.active_weights.copy(),
                "excluded_tools": session.excluded_tools.copy(),
            },
        )

    def _extract_skill_name(self, ctx: ExecutionContext) -> str:
        """从意图参数中提取技能名称

        优先使用 "skill_name" 参数，其次 "strategy_name"，
        若均未提供则使用基于时间戳的默认名称。

        Args:
            ctx: 执行上下文

        Returns:
            str: 提取或生成的技能名称
        """
        if ctx.intent:
            name = ctx.intent.parameters.get("skill_name", "")
            if name:
                return name
            name = ctx.intent.parameters.get("strategy_name", "")
            if name:
                return name
        return f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _validate_state(self, session: DiagnosisSession) -> None:
        """验证当前状态是否允许保存技能

        Args:
            session: 当前诊断会话

        Raises:
            InvalidStateError: 当前状态不允许执行保存技能操作
        """
        if not self.state_machine.can_execute(session, "save_skill"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许保存技能"
            )

    def _ensure_skills_dir(self) -> None:
        """确保技能目录存在"""
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def _build_skill_md(self, session: DiagnosisSession, name: str) -> str:
        """从会话状态构建 Markdown 技能内容

        生成包含描述、推荐工具配置表、诊断流程、
        报告结构和排除工具列表的 Markdown 文档。

        Args:
            session: 当前诊断会话
            name: 技能名称

        Returns:
            str: 生成的 Markdown 内容
        """
        lines: list[str] = []

        # 标题
        lines.append(f"# {name}")
        lines.append("")

        # 描述
        lines.append("## 描述")
        lines.append("")
        lines.append(f"- **会话ID**: {session.session_id}")
        lines.append(f"- **线路名称**: {session.line_name}")
        lines.append(f"- **创建时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 推荐工具配置
        lines.append("## 推荐工具配置")
        lines.append("")
        lines.append("| 工具 | 权重 | 条件 |")
        lines.append("|------|------|------|")

        # 收集所有需要展示的工具
        tools_to_show: dict[str, float] = {}

        # 从 active_weights 添加（排除 excluded_tools）
        for tool_name, weight in session.active_weights.items():
            if tool_name not in session.excluded_tools:
                tools_to_show[tool_name] = weight

        # 从 included_tools 添加（不在 active_weights 中的，权重设为 1.0）
        for tool_name in session.included_tools:
            if tool_name not in tools_to_show and tool_name not in session.excluded_tools:
                tools_to_show[tool_name] = 1.0

        # 按工具名称排序生成表格行
        for tool_name in sorted(tools_to_show.keys()):
            weight = tools_to_show[tool_name]
            # 判断条件：如果在 active_weights 中则为"始终启用"，
            # 如果在 included_tools 但不在 active_weights 中为"用户动态加入"
            if tool_name in session.active_weights:
                condition = "始终启用"
            else:
                condition = "用户动态加入"
            lines.append(f"| {tool_name} | {weight} | {condition} |")

        lines.append("")

        # 诊断流程
        lines.append("## 诊断流程")
        lines.append("")
        lines.append("1. 收集故障上下文信息（线路、杆塔、时间、气象等）")
        lines.append("2. 根据推荐工具配置并行执行诊断工具")
        lines.append("3. 汇总各工具诊断结果并计算置信度")
        lines.append("4. 生成诊断摘要和初步结论")
        lines.append("")

        # 报告结构
        lines.append("## 报告结构")
        lines.append("")
        lines.append("1. 故障概述")
        lines.append("2. 诊断依据")
        lines.append("3. 工具分析结果")
        lines.append("4. 综合评估")
        lines.append("5. 建议措施")
        lines.append("")

        # 排除的工具
        if session.excluded_tools:
            lines.append("## 排除的工具")
            lines.append("")
            for tool_name in sorted(session.excluded_tools):
                lines.append(f"- {tool_name}")
            lines.append("")

        return "\n".join(lines)

    def _save_to_file(self, name: str, content: str) -> Path:
        """将技能内容持久化到 Markdown 文件

        Args:
            name: 技能名称（用作文件名）
            content: Markdown 内容

        Returns:
            Path: 保存的文件路径
        """
        file_path = self.skills_dir / f"{name}.md"
        file_path.write_text(content, encoding="utf-8")
        return file_path

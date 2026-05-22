"""保存技能 Command

将当前会话的调整保存为符合 Agent Skill 规范的 Markdown 文件，
使用 LLM 生成完整的 Skill 内容（YAML frontmatter + pushy description + 完整规则）。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import yaml

from src.core.models import DiagnosisSession, Event, ExecutionContext, SessionStatus
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.skill_loader import SkillLoader
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = Path("skills")


class SaveSkillCommand(Command):
    """保存技能 Command"""

    def __init__(
        self,
        llm_service: LLMService,
        session_manager: SessionManager,
        state_machine: StateMachine,
        skill_loader: SkillLoader,
        skills_dir: Path | None = None,
    ):
        self.llm = llm_service
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.skill_loader = skill_loader
        self.skills_dir = skills_dir or DEFAULT_SKILLS_DIR

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行保存技能操作"""
        session = ctx.session
        skill_name = self._extract_skill_name(ctx)

        yield Event.thinking(
            session.session_id,
            f"保存技能: {skill_name}...",
        )

        self._validate_state(session)
        self._ensure_skills_dir()

        # 收集会话完整状态
        skill_config = self._build_skill_config(session, skill_name)

        # 使用 LLM 生成符合 Agent Skill 规范的 Markdown
        prompt = self._build_generation_prompt(skill_config)
        skill_md = await self.llm.chat([
            {"role": "system", "content": "你是 Skill 生成专家。将诊断配置转换为符合 Agent Skill 规范的 Markdown Skill 文件。"},
            {"role": "user", "content": prompt},
        ])

        file_path = self._save_to_file(skill_name, skill_md)

        session.active_skill_name = skill_name
        self.session_manager._persist()

        logger.info(f"技能已保存: {session.session_id} -> {file_path}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"技能 '{skill_name}' 已保存",
                "skill_name": skill_name,
                "file_path": str(file_path),
            },
        )

    def _extract_skill_name(self, ctx: ExecutionContext) -> str:
        if ctx.intent:
            name = ctx.intent.parameters.get("skill_name", "")
            if name:
                return name
            name = ctx.intent.parameters.get("strategy_name", "")
            if name:
                return name
        return f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _validate_state(self, session: DiagnosisSession) -> None:
        if not self.state_machine.can_execute(session, "save_strategy"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许保存技能"
            )

    def _ensure_skills_dir(self) -> None:
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def _build_skill_config(self, session: DiagnosisSession, name: str) -> dict:
        """收集会话状态构建 Skill 配置。"""
        weights = session.active_weights.copy()
        excluded = session.excluded_tools.copy()

        action_summary = []
        for action in session.action_log:
            action_summary.append({
                "type": action.action_type,
                "params": action.parameters,
                "time": action.timestamp.isoformat(),
            })

        return {
            "name": name,
            "line_context": session.line_name,
            "weights": weights,
            "excluded_tools": excluded,
            "template_name": session.active_template_name,
            "action_history": action_summary,
        }

    def _build_generation_prompt(self, config: dict) -> str:
        weights_yaml = yaml.dump({"weights": config["weights"]}, allow_unicode=True)
        excluded_str = "\n".join(f"- {t}" for t in config["excluded_tools"]) or "无"

        action_lines = []
        for a in config["action_history"]:
            params = a["params"]
            if a["type"] == "exclude":
                action_lines.append(f"- 排除 {params.get('tool_name', '')}")
            elif a["type"] == "adjust_weight":
                action_lines.append(f"- 调整 {params.get('tool_name', '')} 权重为 {params.get('weight', '')}")
            elif a["type"] == "modify_report":
                action_lines.append(f"- 修改报告：{params.get('instruction', '')}")
            elif a["type"] == "complete":
                action_lines.append("- 完成诊断")

        return f"""请根据以下诊断配置，生成一个符合 Agent Skill 规范的 Markdown 文件。

## 配置信息

- 技能名称：{config['name']}
- 线路上下文：{config['line_context']}
- 激活模板：{config['template_name'] or '默认模板'}

### 工具权重配置
```yaml
{weights_yaml}
```

### 排除的工具
{excluded_str}

### 用户操作历史
{"\n".join(action_lines) or "无"}

## 生成要求

1. YAML frontmatter 必须包含 name 和 description（description 要 pushy，明确触发条件）
2. 必须包含"核心算法：加权置信度"章节，明确写出计算公式
3. 工具调用策略表必须反映排除的工具（标记为"跳过"或说明条件）
4. 诊断流程必须基于用户操作历史优化
5. 注意事项中体现用户的偏好设置
6. 末尾添加"历史优化记录"章节，说明本技能的来源
7. 格式与 comprehensive_diagnosis.md 一致

请直接输出 Markdown 内容，不要添加代码块标记。
"""

    def _save_to_file(self, name: str, content: str) -> Path:
        file_path = self.skills_dir / f"{name}.md"
        file_path.write_text(content, encoding="utf-8")
        if hasattr(self.skill_loader, '_cache'):
            self.skill_loader._cache[name] = content
        return file_path

"""报告撰写器

通过单次 LLM 调用生成完整的诊断报告。
"""

import json
import logging
from typing import Any, Dict, Optional

from src.core.models import TemplateConfig, ToolOutput
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)

DEFAULT_CHAPTERS = ["概述", "故障分析", "诊断证据", "诊断结论", "处理建议"]


class ReportComposer:
    """报告撰写器

    基于工具输出和模板配置，通过单次 LLM 调用生成完整诊断报告。
    """

    def __init__(self, llm_service: LLMService):
        """初始化报告撰写器。

        Args:
            llm_service: LLM 服务实例，用于生成报告内容。
        """
        self.llm = llm_service

    async def compose(
        self,
        tool_outputs: Dict[str, ToolOutput],
        template: Optional[TemplateConfig],
        session_id: str,
    ) -> Dict[str, Any]:
        """撰写完整诊断报告。

        通过单次 LLM 调用生成包含所有章节的完整报告。

        Args:
            tool_outputs: 各诊断工具的输出结果，键为工具名，值为 ToolOutput。
            template: 报告模板配置，若为 None 则使用默认章节。
            session_id: 当前会话 ID，用于日志追踪。

        Returns:
            包含 summary 和 report 的字典。
                - summary: 诊断摘要（故障类型、置信度、主工具）
                - report: 格式化后的完整报告 Markdown 字符串。
        """
        # 确定章节列表
        if template and template.chapters:
            chapters = [c.title for c in template.chapters]
        else:
            chapters = DEFAULT_CHAPTERS.copy()

        # 构建提示词
        prompt = self._build_prompt(tool_outputs, chapters)

        # 调用 LLM
        messages = [
            {"role": "system", "content": "你是输电线路故障诊断报告撰写专家。"},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm.chat(messages)
        except Exception as e:
            logger.error(f"会话 {session_id} 报告生成失败: {e}")
            raise

        # 格式化响应
        formatted = self._format_response(response)
        summary = self._extract_summary(tool_outputs)
        return {"summary": summary, "report": formatted}

    def _build_prompt(self, tool_outputs: Dict[str, ToolOutput], chapters: list[str]) -> str:
        """构建 LLM 提示词。

        Args:
            tool_outputs: 工具输出字典。
            chapters: 报告章节标题列表。

        Returns:
            完整的提示词字符串。
        """
        lines = [
            "请根据以下诊断工具输出，生成一份完整的输电线路故障诊断报告。",
            "",
            "## 诊断工具输出",
            "",
        ]

        for tool_name, output in tool_outputs.items():
            lines.append(f"### {tool_name}")
            if output.raw_text:
                lines.append(f"原始文本：\n{output.raw_text}")
            if output.structured_data:
                lines.append(
                    f"结构化数据：\n```json\n"
                    f"{json.dumps(output.structured_data, ensure_ascii=False, indent=2)}"
                    f"\n```"
                )
            lines.append("")

        lines.extend([
            "## 报告要求",
            "",
            "请生成包含以下章节的完整报告：",
            "",
        ])
        for chapter in chapters:
            lines.append(f"- {chapter}")
        lines.extend([
            "",
            "格式要求：",
            "1. 每个章节使用 `## 章节名` 作为标题",
            "2. 内容专业、逻辑清晰",
            "3. 基于提供的诊断数据进行分析",
            "4. 使用 Markdown 格式输出",
        ])

        return "\n".join(lines)

    def _format_response(self, response: str) -> str:
        """格式化 LLM 响应。

        确保报告以一级标题开头。

        Args:
            response: LLM 返回的原始字符串。

        Returns:
            格式化后的报告字符串。
        """
        stripped = response.strip()
        if not stripped.startswith("# "):
            return f"# 输电线路故障诊断报告\n\n{stripped}"
        return stripped

    def _extract_summary(self, tool_outputs: Dict[str, ToolOutput]) -> Dict[str, Any]:
        """从工具输出中提取诊断摘要。

        取置信度最高的工具结果作为 primary diagnosis。
        """
        best_tool = None
        best_confidence = 0.0
        best_fault_type = "未知"

        for tool_name, output in tool_outputs.items():
            structured = output.structured_data or {}
            confidence = structured.get("confidence", 0.0)
            fault_type = structured.get("fault_type", "未知")
            if isinstance(confidence, (int, float)) and confidence > best_confidence:
                best_confidence = confidence
                best_fault_type = fault_type
                best_tool = tool_name

        return {
            "fault_type": best_fault_type,
            "confidence": round(best_confidence, 2),
            "primary_tool": best_tool or "unknown",
        }

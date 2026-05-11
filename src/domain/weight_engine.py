"""权重引擎

计算加权诊断结果。
"""

import logging
from typing import Dict, List

from src.core.models import DiagnosisResult, DiagnosisSummary, ToolOutput
from src.core.exceptions import WeightValidationError

logger = logging.getLogger(__name__)


class WeightEngine:
    """权重引擎"""

    def __init__(self, min_weight: float = 0.1, max_weight: float = 2.0):
        self.min_weight = min_weight
        self.max_weight = max_weight

    def validate(self, weights: Dict[str, float]) -> None:
        """验证权重合法性"""
        for tool_name, weight in weights.items():
            if weight < self.min_weight or weight > self.max_weight:
                raise WeightValidationError(
                    f"权重 {tool_name}={weight} 超出范围 [{self.min_weight}, {self.max_weight}]"
                )

    def compute(
        self,
        tool_outputs: Dict[str, ToolOutput],
        weights: Dict[str, float],
    ) -> DiagnosisSummary:
        """计算加权诊断结果

        Args:
            tool_outputs: 各工具的输出
            weights: 权重配置

        Returns:
            DiagnosisSummary: 加权后的诊断摘要
        """
        self.validate(weights)

        results: List[DiagnosisResult] = []
        confidence_distribution: Dict[str, float] = {}
        weighted_scores: Dict[str, float] = {}

        for tool_name, output in tool_outputs.items():
            weight = weights.get(tool_name, 1.0)

            # 从工具输出中提取置信度（如果有）
            confidence = self._extract_confidence(output)
            weighted_confidence = confidence * weight

            result = DiagnosisResult(
                fault_type=tool_name.replace("DiagnosisTool", ""),
                confidence=confidence,
                confidence_level=self._level_from_confidence(confidence),
                evidence=self._extract_evidence(output),
                details=output.structured_data or {},
                tool_name=tool_name,
            )
            results.append(result)
            confidence_distribution[tool_name] = confidence
            weighted_scores[tool_name] = weighted_confidence

        # 确定主要诊断（加权后最高分）
        primary = None
        if results:
            primary = max(results, key=lambda r: weighted_scores.get(r.tool_name, 0))

        return DiagnosisSummary(
            results=results,
            primary_diagnosis=primary,
            all_evidence=[e for r in results for e in r.evidence],
            confidence_distribution=confidence_distribution,
            weights=weights,
            weighted_scores=weighted_scores,
        )

    def _extract_confidence(self, output: ToolOutput) -> float:
        """从工具输出中提取置信度"""
        if output.structured_data:
            # 尝试从结构化数据中提取
            for key in ["confidence", "confidence_score", "match_score", "risk_score"]:
                if key in output.structured_data:
                    value = output.structured_data[key]
                    if isinstance(value, (int, float)):
                        return float(value)
        return 0.5  # 默认置信度

    def _extract_evidence(self, output: ToolOutput) -> List[str]:
        """从工具输出中提取证据"""
        evidence = []
        if output.raw_text:
            evidence.append(output.raw_text[:200])  # 截断避免过长
        if output.structured_data:
            for key, value in output.structured_data.items():
                evidence.append(f"{key}: {value}")
        return evidence

    def _level_from_confidence(self, confidence: float) -> str:
        """根据置信度判断等级"""
        from src.core.models import ConfidenceLevel
        if confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.4:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

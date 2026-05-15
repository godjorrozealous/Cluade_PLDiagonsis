"""技能加载器

提供 Markdown 格式技能文件的加载、列表、保存和删除功能。
支持内存缓存，并在文件缺失时提供默认回退内容。
"""

import logging
import re
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)

DEFAULT_SKILL_CONTENT = """# 默认技能

## 描述

这是一个默认技能占位符。当请求的技能文件不存在时，系统将返回此内容。

## 用法

请确保技能文件已正确放置在 `skills/` 目录下，并以 `.md` 为扩展名。

## 注意事项

- 技能文件名应使用小写字母和下划线
- 内容使用 Markdown 格式编写
- 每个技能应包含描述、参数说明和示例
"""


class SkillLoader:
    """技能加载器

    负责管理 Markdown 技能文件的 CRUD 操作，并维护内存缓存以提高读取性能。
    """

    def __init__(self, skills_dir: str = "skills") -> None:
        """初始化技能加载器。

        Args:
            skills_dir: 技能文件存放目录，默认为 "skills"。
        """
        self._skills_dir = Path(skills_dir)
        self._cache: Dict[str, str] = {}

    def load(self, skill_name: str) -> tuple[str, dict]:
        """加载指定技能文件的内容和权重配置。

        如果内容已缓存，直接返回缓存内容。
        如果文件不存在，返回默认回退内容。

        Args:
            skill_name: 技能名称（不含 .md 扩展名）。

        Returns:
            (技能文件内容, 权重配置字典)
        """
        if skill_name in self._cache:
            logger.debug(f"命中缓存: {skill_name}")
            content = self._cache[skill_name]
            return content, self._extract_weights(content)

        skill_path = self._skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            logger.warning(f"技能文件不存在: {skill_path}，返回默认内容")
            return DEFAULT_SKILL_CONTENT, {}

        content = skill_path.read_text(encoding="utf-8")
        self._cache[skill_name] = content
        logger.info(f"已加载技能: {skill_name}")
        return content, self._extract_weights(content)

    def _extract_weights(self, content: str) -> dict[str, float]:
        """从 Markdown 内容中提取 YAML 代码块里的 weights 配置。"""
        pattern = r'```yaml\s*(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}
        try:
            config = yaml.safe_load(match.group(1))
            if isinstance(config, dict):
                return config.get("weights", {})
        except yaml.YAMLError:
            pass
        return {}

    def list_skills(self) -> List[str]:
        """列出所有可用的技能名称。

        Returns:
            按字母顺序排序的技能名称列表（不含 .md 扩展名）。
        """
        if not self._skills_dir.exists():
            logger.warning(f"技能目录不存在: {self._skills_dir}")
            return []

        skills = sorted(
            p.stem for p in self._skills_dir.glob("*.md") if p.is_file()
        )
        logger.debug(f"发现 {len(skills)} 个技能")
        return skills

    def save(self, skill_name: str, content: str) -> Path:
        """保存技能文件内容。

        自动创建 skills_dir 目录（如不存在），并更新缓存。

        Args:
            skill_name: 技能名称（不含 .md 扩展名）。
            content: 要写入的 Markdown 内容。

        Returns:
            写入文件的路径。
        """
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        skill_path = self._skills_dir / f"{skill_name}.md"
        skill_path.write_text(content, encoding="utf-8")
        self._cache[skill_name] = content
        logger.info(f"已保存技能: {skill_name}")
        return skill_path

    def delete(self, skill_name: str) -> bool:
        """删除指定技能文件。

        如文件存在则删除并清除缓存；如不存在则返回 False。

        Args:
            skill_name: 技能名称（不含 .md 扩展名）。

        Returns:
            是否成功删除文件。
        """
        skill_path = self._skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            logger.warning(f"删除失败，技能文件不存在: {skill_path}")
            return False

        skill_path.unlink()
        self._cache.pop(skill_name, None)
        logger.info(f"已删除技能: {skill_name}")
        return True

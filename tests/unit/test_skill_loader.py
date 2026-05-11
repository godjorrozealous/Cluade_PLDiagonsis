"""Tests for src/domain/skill_loader.py — load, list, save, delete skills."""

import pytest

from src.domain.skill_loader import DEFAULT_SKILL_CONTENT, SkillLoader


# ============================================================================
# load
# ============================================================================


def test_load_default_skill(tmp_path) -> None:
    """load() returns file content for an existing skill."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_file = skills_dir / "test_skill.md"
    expected_content = "# Test Skill\n\nThis is a test skill."
    skill_file.write_text(expected_content, encoding="utf-8")

    loader = SkillLoader(skills_dir=str(skills_dir))
    result = loader.load("test_skill")

    assert result == expected_content


def test_load_missing_skill_fallback(tmp_path) -> None:
    """load() returns DEFAULT_SKILL_CONTENT when the skill file is missing."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    loader = SkillLoader(skills_dir=str(skills_dir))
    result = loader.load("nonexistent_skill")

    assert result == DEFAULT_SKILL_CONTENT


# ============================================================================
# list_skills
# ============================================================================


def test_list_skills(tmp_path) -> None:
    """list_skills() returns sorted skill names without .md extension."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "beta_skill.md").write_text("# Beta", encoding="utf-8")
    (skills_dir / "alpha_skill.md").write_text("# Alpha", encoding="utf-8")
    (skills_dir / "gamma_skill.md").write_text("# Gamma", encoding="utf-8")

    loader = SkillLoader(skills_dir=str(skills_dir))
    result = loader.list_skills()

    assert result == ["alpha_skill", "beta_skill", "gamma_skill"]

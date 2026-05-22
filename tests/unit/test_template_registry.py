import pytest
from pathlib import Path

from src.domain.template_registry import TemplateRegistry


class TestTemplateRegistry:
    @pytest.fixture
    def registry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.domain.template_registry.UPLOADS_DIR", tmp_path / "uploads")
        monkeypatch.setattr("src.domain.template_registry.PARSED_DIR", tmp_path / "parsed")
        return TemplateRegistry()

    def test_list_empty(self, registry):
        assert registry.list_templates() == []

    def test_upload_and_parse_markdown(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试模板\n\n## 概述\n")
        result = registry.upload(md_file, "测试模板.md")
        assert result["name"] == "测试模板"
        assert result["parsed"] is True

    def test_activate(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试\n")
        registry.upload(md_file, "测试.md")
        assert registry.activate("测试") is True
        assert registry.get_active() == "测试"

    def test_delete(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试\n")
        registry.upload(md_file, "测试.md")
        assert registry.delete("测试") is True
        assert registry.list_templates() == []

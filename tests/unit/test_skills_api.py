"""Tests for skills REST API endpoints."""

import json
from pathlib import Path

import pytest

from src.interfaces.web import create_app


class TestListSkills:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_list_skills_empty(self, client):
        """GET /api/skills returns empty list when no strategies exist."""
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "strategies" in data
        assert data["strategies"] == []

    def test_list_skills_returns_saved(self, client, tmp_path):
        """GET /api/skills returns strategies from skills/ directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        strategy_file = skills_dir / "my_strategy.json"
        strategy_file.write_text(
            json.dumps(
                {
                    "name": "my_strategy",
                    "description": "Test strategy",
                    "created_at": "2025-05-11T10:00:00",
                    "tool_weights": {"LightningDiagnosisTool": 1.5},
                    "excluded_tools": ["WindDiagnosisTool"],
                }
            ),
            encoding="utf-8",
        )

        # Patch the skills directory via monkeypatch on Path.glob
        original_glob = Path.glob

        def patched_glob(self, pattern):
            if str(self) == "skills" and pattern == "*.json":
                return list(skills_dir.glob("*.json"))
            return original_glob(self, pattern)

        Path.glob = patched_glob
        try:
            resp = client.get("/api/skills")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["strategies"]) == 1
            assert data["strategies"][0]["name"] == "my_strategy"
            assert data["strategies"][0]["description"] == "Test strategy"
            assert data["strategies"][0]["tool_weights"]["LightningDiagnosisTool"] == 1.5
        finally:
            Path.glob = original_glob


class TestDeleteSkill:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_delete_missing_strategy(self, client):
        """DELETE /api/skills/<name> returns 404 for missing strategy."""
        resp = client.delete("/api/skills/nonexistent")
        assert resp.status_code == 404
        assert "不存在" in resp.get_json()["error"]


class TestResetSkills:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_reset_no_active_session(self, client):
        """POST /api/skills/reset returns 400 without active session."""
        resp = client.post("/api/skills/reset")
        assert resp.status_code == 400
        assert "没有活跃的会话" in resp.get_json()["error"]

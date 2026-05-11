"""Flask Web 接口

仅负责路由和 SSE 流式输出，不处理业务逻辑。
Flask 3.x 原生支持 async 视图函数，无需额外包装。
"""

import asyncio
import json
import logging
from datetime import datetime

import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

from src.core.models import Event, EventType, IntentType, SessionStatus
from src.application.commands.diagnose import DiagnoseCommand
from src.application.commands.exclude import ExcludeToolCommand
from src.application.commands.recheck import RecheckToolCommand
from src.application.commands.adjust_weight import AdjustWeightCommand
from src.application.commands.save_strategy import SaveStrategyCommand
from src.application.context import ContextBuilder
from src.interfaces.dependency_injection import get_container

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    container = get_container()

    @app.before_request
    def _ensure_container_init() -> None:
        """确保容器已初始化（惰性初始化）"""
        if not getattr(container, "_initialized", False):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # 在异步上下文中，使用 create_task 初始化
                asyncio.create_task(container.init())
            else:
                asyncio.run(container.init())
            container._initialized = True

    # ------------------------------------------------------------------
    # SSE 聊天接口
    # ------------------------------------------------------------------
    @app.route("/chat", methods=["POST"])
    def chat():
        """流式对话接口"""
        data = request.json or {}
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "消息不能为空"}), 400

        return Response(
            stream_with_context(_sync_chat_stream(user_message)),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    def _sync_chat_stream(message: str):
        """同步包装器：将 async generator 桥接到 Flask WSGI"""
        async def _async_stream():
            async for event in _chat_stream(message):
                yield event

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        gen = _async_stream()
        try:
            while True:
                yield loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    async def _chat_stream(message: str):
        """聊天流生成器（异步）"""
        try:
            # 1. 获取或创建会话
            session = container.session_manager.get_or_create(message)

            # 2. 意图识别
            yield _sse_event(Event.thinking(session.session_id, "理解用户意图..."))
            intent = await container.intent_classifier.classify(message, session)

            # 3. 构建执行上下文
            ctx = ContextBuilder.build(session, message, intent=intent)

            # 4. 路由到对应 Command
            cmd = _resolve_command(intent.intent_type, container)
            if cmd is not None:
                async for event in cmd.execute(ctx):
                    yield _sse_event(event)
            else:
                # 通用对话
                response = await container.llm_service.chat(
                    [
                        {"role": "system", "content": "你是输电线路故障诊断助手。"},
                        {"role": "user", "content": message},
                    ]
                )
                yield _sse_event(Event.complete(session.session_id, {"message": response}))

        except Exception as e:
            logger.error(f"处理失败: {e}")
            yield _sse_event(Event.error("", str(e)))

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------
    @app.route("/api/sessions", methods=["GET"])
    def list_sessions():
        """获取会话列表"""
        sessions = container.session_manager.list_sessions()
        return jsonify(
            {
                "sessions": [
                    {
                        "id": s.session_id,
                        "line_name": s.line_name,
                        "status": s.status.value,
                        "created_at": s.created_at.isoformat(),
                        "updated_at": s.updated_at.isoformat(),
                    }
                    for s in sessions
                ]
            }
        )

    @app.route("/api/sessions/<id>/switch", methods=["POST"])
    def switch_session(id: str):
        """切换会话"""
        try:
            session = container.session_manager.switch_active(id)
            return jsonify(
                {
                    "session_id": session.session_id,
                    "line_name": session.line_name,
                    "status": session.status.value,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/api/tools", methods=["GET"])
    def list_tools():
        """获取诊断工具列表"""
        tools = container.tool_registry.list_tools()
        return jsonify(
            {
                "tools": [
                    {
                        "name": t.name,
                        "display_name": t.display_name,
                        "description": t.description,
                        "category": t.category,
                    }
                    for t in tools
                ]
            }
        )

    @app.route("/api/sessions/<id>", methods=["GET"])
    def get_session(id: str):
        """获取会话详情"""
        try:
            session = container.session_manager.get(id)
            return jsonify(
                {
                    "session_id": session.session_id,
                    "line_name": session.line_name,
                    "status": session.status.value,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "active_weights": session.active_weights,
                    "excluded_tools": session.excluded_tools,
                    "rechecked_tools": session.rechecked_tools,
                    "summaries": [
                        {
                            "version": s.version,
                            "primary_diagnosis": (
                                s.primary_diagnosis.fault_type
                                if s.primary_diagnosis
                                else None
                            ),
                            "confidence": (
                                s.primary_diagnosis.confidence
                                if s.primary_diagnosis
                                else 0
                            ),
                            "created_at": s.created_at.isoformat(),
                        }
                        for s in session.summaries
                    ],
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/api/health", methods=["GET"])
    def health():
        """健康检查"""
        return jsonify({"status": "ok", "version": "0.2.0"})

    @app.route("/api/sessions/clear", methods=["POST"])
    def clear_sessions():
        """清空所有会话"""
        try:
            sessions = container.session_manager.list_sessions()
            count = len(sessions)
            for session in sessions:
                container.session_manager._sessions.pop(session.session_id, None)
            container.session_manager._active_session_id = None
            container.session_manager._persist()
            return jsonify({"success": True, "message": f"已清空 {count} 个会话"})
        except Exception as e:
            logger.error(f"清空会话失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        """获取系统设置"""
        from src.core.models import DEFAULT_WEIGHTS

        return jsonify(
            {
                "default_weights": DEFAULT_WEIGHTS,
                "weight_range": {
                    "min": container.config.diagnosis.weight_min,
                    "max": container.config.diagnosis.weight_max,
                },
                "llm": {
                    "provider": container.config.llm.provider,
                    "model": container.config.llm.model,
                },
            }
        )

    @app.route("/api/settings/weights", methods=["POST"])
    def update_settings_weights():
        """更新默认权重配置"""
        data = request.json or {}
        weights = data.get("weights", {})

        if not weights:
            return jsonify({"error": "weights 不能为空"}), 400

        try:
            # 更新当前活跃会话的权重
            session = container.session_manager.get_active()
            if session:
                container.session_manager.update_weights(session.session_id, weights)
                return jsonify(
                    {
                        "success": True,
                        "message": "权重已更新",
                        "weights": session.active_weights,
                    }
                )
            return jsonify({"error": "没有活跃的会话"}), 400
        except Exception as e:
            logger.error(f"更新权重失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 技能管理 API（Markdown 格式）
    # ------------------------------------------------------------------
    @app.route("/api/skills", methods=["GET"])
    def list_skills():
        """获取所有技能文件"""
        skill_names = container.skill_loader.list_skills()
        skills = []
        for name in skill_names:
            try:
                content = container.skill_loader.load(name)
                # 解析第一行标题作为描述
                description = ""
                for line in content.splitlines():
                    if line.startswith("# "):
                        description = line[2:].strip()
                        break
                skills.append(
                    {
                        "name": name,
                        "description": description,
                    }
                )
            except Exception as e:
                logger.warning(f"读取技能文件失败 {name}: {e}")
        return jsonify({"skills": skills})

    @app.route("/api/skills", methods=["POST"])
    def create_skill():
        """创建新技能文件"""
        data = request.get_json(force=True) or {}
        name = data.get("name", "").strip()
        content = data.get("content", "").strip()

        if not name:
            return jsonify({"error": "技能名称不能为空"}), 400
        if not content:
            return jsonify({"error": "技能内容不能为空"}), 400

        try:
            container.skill_loader.save(name, content)
            return jsonify(
                {
                    "success": True,
                    "message": f"技能 '{name}' 已保存",
                    "name": name,
                }
            )
        except Exception as e:
            logger.error(f"保存技能失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/skills/<name>/activate", methods=["POST"])
    def activate_skill(name: str):
        """激活技能到当前会话"""
        session = container.session_manager.get_active()
        if not session:
            return jsonify({"error": "没有活跃的会话"}), 400

        skill_names = container.skill_loader.list_skills()
        if name not in skill_names:
            return jsonify({"error": f"技能 '{name}' 不存在"}), 404

        try:
            session.active_skill_name = name
            return jsonify(
                {
                    "success": True,
                    "skill_name": name,
                    "message": f"技能 '{name}' 已激活",
                }
            )
        except Exception as e:
            logger.error(f"激活技能失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/skills/<name>", methods=["DELETE"])
    def delete_skill(name: str):
        """删除技能"""
        if not container.skill_loader.delete(name):
            return jsonify({"error": f"技能 '{name}' 不存在"}), 404

        return jsonify({"success": True, "message": f"技能 '{name}' 已删除"})

    @app.route("/api/skills/discover", methods=["POST"])
    def discover_tools():
        """手动触发工具扫描，返回新工具列表"""
        try:
            available_tools = container.tool_registry.list_tools()
            tool_names = [t.name for t in available_tools]
            return jsonify(
                {
                    "success": True,
                    "tools": tool_names,
                    "count": len(tool_names),
                }
            )
        except Exception as e:
            logger.error(f"工具扫描失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/skills/reset", methods=["POST"])
    def reset_skills():
        """重置当前会话为默认策略"""
        session = container.session_manager.get_active()
        if not session:
            return jsonify({"error": "没有活跃的会话"}), 400

        from src.core.models import DEFAULT_WEIGHTS

        container.session_manager.update_weights(
            session.session_id, DEFAULT_WEIGHTS.copy()
        )
        # 清空排除列表
        for tool in list(session.excluded_tools):
            container.session_manager.include_tool(session.session_id, tool)

        session.active_skill_name = None

        return jsonify(
            {
                "success": True,
                "message": "已重置为默认策略",
                "default_weights": DEFAULT_WEIGHTS,
            }
        )

    # ------------------------------------------------------------------
    # 静态文件服务（前端 dist）
    # ------------------------------------------------------------------
    dist_dir = Path(os.getenv("FRONTEND_DIST", "web/dist")).resolve()

    if dist_dir.exists():

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path: str):
            """服务前端静态文件"""
            file_path = dist_dir / path
            if file_path.is_file():
                return send_from_directory(dist_dir, path)
            return send_from_directory(dist_dir, "index.html")

    return app


def _resolve_command(intent_type: IntentType, container):
    """根据意图类型解析对应的 Command 实例"""
    if intent_type == IntentType.DIAGNOSE:
        return DiagnoseCommand(
            tool_registry=container.tool_registry,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
            event_bus=container.event_bus,
            skill_loader=container.skill_loader,
            prompt_builder=container.prompt_builder,
            diagnosis_planner=container.diagnosis_planner,
            tool_executor=container.tool_executor,
            report_composer=container.report_composer,
        )
    elif intent_type == IntentType.EXCLUDE_TOOL:
        return ExcludeToolCommand(
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.RECHECK_TOOL:
        return RecheckToolCommand(
            tool_registry=container.tool_registry,
            weight_engine=container.weight_engine,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.ADJUST_WEIGHT:
        return AdjustWeightCommand(
            weight_engine=container.weight_engine,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.SAVE_STRATEGY:
        return SaveStrategyCommand(
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    return None


def _sse_event(event: Event) -> str:
    """格式化 SSE 事件"""

    def _serialize(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_serialize(v) for v in obj]
        return obj

    data = {
        "event_type": event.event_type.value,
        "session_id": event.session_id,
        "payload": _serialize(event.payload),
        "timestamp": event.timestamp.isoformat(),
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

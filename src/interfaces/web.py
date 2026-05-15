"""Flask Web 接口

仅负责路由和 SSE 流式输出，不处理业务逻辑。
Flask 3.x 原生支持 async 视图函数，无需额外包装。
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

from src.core.models import Event, EventType, IntentType, SessionStatus
from src.application.commands.diagnose import DiagnoseCommand
from src.application.commands.exclude import ExcludeToolCommand
from src.application.commands.include_tool import IncludeToolCommand
from src.application.commands.recheck import RecheckToolCommand
from src.application.commands.adjust_weight import AdjustWeightCommand
from src.application.commands.save_strategy import SaveStrategyCommand
from src.application.commands.complete_diagnosis import CompleteDiagnosisCommand
from src.application.context import ContextBuilder
from src.interfaces.dependency_injection import get_container
from src.infrastructure.fault_parser import FaultContextParser

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

    def _append_chat_message(session, role: str, content: str, event_type: str = None):
        """追加聊天记录到会话"""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if event_type:
            msg["event_type"] = event_type
        session.chat_history.append(msg)

    async def _chat_stream(message: str):
        """聊天流生成器（异步）"""
        session = None
        try:
            # 1. 意图识别（先识别意图，再决定如何获取会话）
            intent = await container.intent_classifier.classify(message, None)
            intent_type = intent.intent_type

            # 2. 获取会话：诊断类意图从消息中提取线路，其他意图使用活跃会话
            if intent_type == IntentType.DIAGNOSE:
                fault_ctx = FaultContextParser.parse(message, "")
                line_name = fault_ctx.line_name or message
                session = container.session_manager.get_or_create(
                    line_name, fault_context=fault_ctx
                )
            else:
                session = container.session_manager.get_active()
                if session is None:
                    yield _sse_event(
                        Event.error("", "没有活跃的会话，请先开始诊断")
                    )
                    return

            # 保存用户消息
            _append_chat_message(session, "user", message)

            yield _sse_event(
                Event.start(
                    session.session_id,
                    {"message": "开始诊断...", "line_name": session.line_name},
                )
            )
            yield _sse_event(Event.thinking(session.session_id, "理解用户意图..."))

            # 重新分类（带会话上下文）以获得更准确的参数提取
            intent = await container.intent_classifier.classify(message, session)

            # 3. 构建执行上下文
            ctx = ContextBuilder.build(session, message, intent=intent)

            # 4. 路由到对应 Command
            cmd = _resolve_command(intent.intent_type, container)
            if cmd is not None:
                async for event in cmd.execute(ctx):
                    yield _sse_event(event)
                    if event.event_type in (EventType.COMPLETE, EventType.ERROR):
                        _append_chat_message(
                            session,
                            "assistant",
                            event.payload.get("message", ""),
                            event.event_type.value,
                        )

                # 自动链式诊断：排除/恢复工具后无条件自动重新诊断
                if intent_type in (IntentType.EXCLUDE_TOOL, IntentType.INCLUDE_TOOL):
                    yield _sse_event(
                        Event.thinking(session.session_id, "自动重新诊断...")
                    )
                    diagnose_cmd = DiagnoseCommand(
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
                    async for event in diagnose_cmd.execute(ctx):
                        yield _sse_event(event)
                        if event.event_type in (EventType.COMPLETE, EventType.ERROR):
                            _append_chat_message(
                                session,
                                "assistant",
                                event.payload.get("message", ""),
                                event.event_type.value,
                            )
            else:
                # 非诊断相关对话，提示用户
                hint = (
                    "您好，我是输电线路故障综合诊断智能体，专注于输电线路跳闸等故障的诊断分析。"
                    "请提供线路名称、电压等级及故障时间等信息，我将为您进行专业诊断。"
                )
                yield _sse_event(Event.complete(session.session_id, {"message": hint}))
                _append_chat_message(session, "assistant", hint, EventType.COMPLETE.value)

            # 持久化聊天记录
            container.session_manager._persist()

        except Exception as e:
            logger.error(f"处理失败: {e}")
            yield _sse_event(Event.error("", str(e)))
            if session:
                _append_chat_message(session, "assistant", str(e), EventType.ERROR.value)
                container.session_manager._persist()

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------
    @app.route("/api/sessions", methods=["GET"])
    def list_sessions():
        """获取会话列表"""
        sessions = container.session_manager.list_sessions()
        result = []
        for s in sessions:
            voltage_level = ""
            fault_time = ""
            if s.current_summary and s.current_summary.fault_context:
                voltage_level = (
                    s.current_summary.fault_context.additional_info.get("voltage_level", "")
                    or ""
                )
                if s.current_summary.fault_context.fault_time:
                    fault_time = s.current_summary.fault_context.fault_time.isoformat()
            result.append(
                {
                    "session_id": s.session_id,
                    "line_name": s.line_name,
                    "status": s.status.value,
                    "voltage_level": voltage_level,
                    "fault_time": fault_time,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
            )
        return jsonify({"sessions": result})

    @app.route("/api/sessions/<id>/switch", methods=["POST"])
    def switch_session(id: str):
        """切换会话"""
        try:
            session = container.session_manager.switch_active(id)
            return jsonify(
                {
                    "success": True,
                    "session_id": session.session_id,
                    "line_name": session.line_name,
                    "status": session.status.value,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/api/sessions/<id>/complete", methods=["POST"])
    def complete_session(id: str):
        """完成诊断，将会话标记为 completed"""
        try:
            session = container.session_manager.get(id)
            container.state_machine.transition(session, SessionStatus.COMPLETED)
            container.session_manager._persist()
            return jsonify(
                {
                    "success": True,
                    "session_id": session.session_id,
                    "line_name": session.line_name,
                    "status": session.status.value,
                }
            )
        except Exception as e:
            logger.error(f"完成诊断失败: {e}")
            return jsonify({"error": str(e)}), 400

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
            # Build latest_summary from current_summary
            latest_summary = None
            if session.current_summary:
                primary = session.current_summary.primary_diagnosis
                latest_summary = {
                    "fault_type": primary.fault_type if primary else "未知",
                    "confidence": primary.confidence if primary else 0,
                    "report": session.latest_report,
                    "line_name": session.line_name,
                    "voltage_level": (
                        session.current_summary.fault_context.additional_info.get("voltage_level", "")
                        if session.current_summary.fault_context
                        and session.current_summary.fault_context.additional_info
                        else ""
                    ),
                }
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
                    "latest_summary": latest_summary,
                    "chat_history": session.chat_history,
                    "action_log": [
                        {
                            "action_type": a.action_type,
                            "tool_name": a.parameters.get("tool_name", ""),
                            "description": a.parameters.get("description", ""),
                            "weight": a.parameters.get("weight"),
                            "timestamp": a.timestamp.isoformat(),
                        }
                        for a in session.action_log
                    ],
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
                content, _ = container.skill_loader.load(name)
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

    @app.route("/api/skills/default", methods=["GET"])
    def get_default_skill():
        """获取全局默认技能"""
        return jsonify({
            "default_skill": container.session_manager._default_skill_name,
            "available_skills": container.skill_loader.list_skills(),
        })

    @app.route("/api/skills/default", methods=["POST"])
    def set_default_skill():
        """设置全局默认技能"""
        data = request.json or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "技能名称不能为空"}), 400
        if name not in container.skill_loader.list_skills():
            return jsonify({"error": f"技能 '{name}' 不存在"}), 404
        container.session_manager.set_default_skill(name)
        container.session_manager._persist()
        return jsonify({"success": True, "default_skill": name})

    @app.route("/api/sessions/<id>/skill-summary", methods=["GET"])
    def generate_skill_summary(id: str):
        """生成技能摘要（基于会话操作历史）"""
        try:
            session = container.session_manager.get(id)
        except Exception as e:
            return jsonify({"error": str(e)}), 404

        excluded = set()
        included = set()
        weight_changes = {}
        report_modifications = []

        for action in session.action_log:
            t = action.action_type
            params = action.parameters
            if t == "exclude":
                excluded.add(params.get("tool_name", ""))
            elif t == "include":
                included.add(params.get("tool_name", ""))
            elif t == "adjust_weight":
                weight_changes[params.get("tool_name", "")] = params.get("weight", 0)
            elif t == "modify_report":
                report_modifications.append(params.get("description", ""))

        final_excluded = excluded - included

        content = f"""# {session.line_name} 诊断策略

## 描述
基于 {session.line_name} 的诊断经验自动生成的策略模板。
适用于类似故障场景的输电线路诊断。

## 默认排除的诊断工具
{chr(10).join(f"- {t}" for t in final_excluded) or "无"}

## 默认权重调整
{chr(10).join(f"- {t}: {v}" for t, v in weight_changes.items()) or "无"}

## 报告模板修改
{chr(10).join(f"- {m}" for m in report_modifications) or "无"}

## 使用说明
激活此技能后，新会话将自动应用上述配置。
"""
        suggested_name = f"{session.line_name}_策略"
        return jsonify({"content": content, "suggested_name": suggested_name})

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
    elif intent_type == IntentType.INCLUDE_TOOL:
        return IncludeToolCommand(
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
    elif intent_type == IntentType.COMPLETE:
        return CompleteDiagnosisCommand(
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

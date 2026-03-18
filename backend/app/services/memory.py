"""会话记忆服务。

Redis 存短期运行态，MySQL 存长期消息历史与快照。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from redis import Redis

from app.core.config import Settings
from app.repositories.store import ShopRepository


class MemoryService:
    """负责会话上下文的读取、缓存和回放。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    def load_runtime_state(self, session_id: str, repo: ShopRepository) -> dict[str, Any]:
        """优先从 Redis 读取短期记忆，失败时回放 MySQL。"""
        return self._load_state(session_id, repo, use_cache=True)

    def rebuild(self, session_id: str, repo: ShopRepository) -> dict[str, Any]:
        """强制忽略 Redis，直接基于 MySQL 重建并写回缓存。"""
        state = self._load_state(session_id, repo, use_cache=False)
        state["memory_source"] = "mysql_rebuild"
        self._write_cache(session_id, state)
        return state

    def _load_state(self, session_id: str, repo: ShopRepository, use_cache: bool) -> dict[str, Any]:
        """统一的状态加载逻辑。"""
        cache_key = self._session_key(session_id)
        if use_cache:
            try:
                cached = self.redis.get(cache_key)
            except Exception:
                cached = None

            if cached:
                state = json.loads(cached)
                state["memory_source"] = "redis"
                return state

        snapshot = repo.get_latest_snapshot(session_id)
        messages = repo.list_recent_messages(session_id, limit=self.settings.chat_history_window)
        if not snapshot and not messages:
            return {"messages": [], "slots": {}, "summary": "", "intent": None, "memory_source": "new"}

        snapshot_state = snapshot.state_json if snapshot else {}
        state = {
            "messages": [{"role": item.role, "content": item.content, "intent": item.intent or ""} for item in messages],
            "slots": snapshot_state.get("slots", {}),
            "summary": snapshot_state.get("summary", ""),
            "intent": snapshot_state.get("intent"),
            "memory_source": "mysql_rebuild",
        }
        self._write_cache(session_id, state)
        return state

    def persist_turn(self, state: dict[str, Any], repo: ShopRepository) -> dict[str, Any]:
        """把当前轮对话同时写入 MySQL 和 Redis。"""
        repo.get_or_create_session(state["session_id"], state["user_id"], state["user_message"])
        repo.update_session_intent(state["session_id"], state.get("intent", "general"))

        # 用户消息和助手消息都需要落库，方便后续调试和回放。
        repo.append_message(
            session_id=state["session_id"],
            role="user",
            content=state["user_message"],
            intent=state.get("intent"),
        )
        repo.append_message(
            session_id=state["session_id"],
            role="assistant",
            content=state["final_reply"],
            intent=state.get("intent"),
            citations=state.get("citations", []),
            tool_calls=state.get("used_tools", []),
        )

        snapshot_state = self._build_snapshot(state)
        repo.save_snapshot(
            session_id=state["session_id"],
            intent=state.get("intent"),
            memory_source=state.get("memory_source", "redis"),
            state=snapshot_state,
        )
        self._write_cache(state["session_id"], snapshot_state)
        return snapshot_state

    def _write_cache(self, session_id: str, payload: dict[str, Any]) -> None:
        """把短期记忆写入 Redis，失败时静默降级。"""
        try:
            self.redis.setex(
                self._session_key(session_id),
                self.settings.memory_ttl_seconds,
                json.dumps(payload, ensure_ascii=False, default=str),
            )
        except Exception:
            return

    def _build_snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        """把本轮状态压缩成下一轮可继续使用的最小上下文。"""
        recent_messages = list(state.get("messages", []))
        recent_messages.append({"role": "user", "content": state["user_message"]})
        recent_messages.append({"role": "assistant", "content": state["final_reply"]})
        return {
            "messages": recent_messages[-self.settings.chat_history_window :],
            "slots": state.get("slots", {}),
            "summary": state.get("summary", ""),
            "intent": state.get("intent"),
            "used_tools": state.get("used_tools", []),
            "updated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        }

    @staticmethod
    def _session_key(session_id: str) -> str:
        """统一 Redis Key 格式，便于后续扩展其他键。"""
        return f"session:{session_id}"

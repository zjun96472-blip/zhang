"""LangGraph 共享状态定义。

图中的每个节点都会读取这里的字段，并在执行后补充自己的输出。
"""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """ShopMate 单轮执行时在图中流转的状态对象。"""

    session_id: str
    user_id: str
    user_message: str
    messages: list[dict[str, Any]]
    summary: str
    memory_source: str
    intent: str
    confidence: float
    missing_fields: list[str]
    slots: dict[str, Any]
    retrieved_docs: list[dict[str, Any]]
    order_context: dict[str, Any] | None
    policy_result: dict[str, Any] | None
    citations: list[dict[str, Any]]
    used_tools: list[str]
    final_reply: str
    needs_handoff: bool
    handoff_reason: str | None
    handoff_ticket_id: str | None
    db: Any

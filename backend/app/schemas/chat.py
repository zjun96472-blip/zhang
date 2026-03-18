"""聊天、会话与工单接口的数据结构定义。"""

from datetime import datetime

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """返回给前端的知识库引用信息。"""

    id: str
    source: str
    doc_type: str
    category: str
    score: float | None = None


class ChatRequest(BaseModel):
    """聊天接口入参。"""

    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    """聊天接口出参，包含回复文本与 Agent 决策摘要。"""

    session_id: str
    reply: str
    intent: str
    citations: list[Citation] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    action: str = "reply"
    memory_source: str
    needs_handoff: bool = False
    handoff_ticket_id: str | None = None


class ChatMessageItem(BaseModel):
    """会话详情页里单条消息的展示结构。"""

    role: str
    content: str
    intent: str | None = None
    citations: list[dict] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    created_at: datetime


class SessionSnapshotItem(BaseModel):
    """保存给调试页使用的运行时状态快照。"""

    intent: str | None = None
    memory_source: str
    state: dict
    created_at: datetime


class SessionSummary(BaseModel):
    """会话列表中的摘要结构。"""

    session_id: str
    title: str
    current_intent: str | None = None
    created_at: datetime
    updated_at: datetime


class SessionResponse(BaseModel):
    """单个会话的完整详情。"""

    session_id: str
    user_id: str
    title: str
    current_intent: str | None = None
    messages: list[ChatMessageItem]
    snapshots: list[SessionSnapshotItem]


class TicketItem(BaseModel):
    """工单列表项。"""

    ticket_no: str
    session_id: str
    user_id: str
    reason: str
    status: str
    summary: str
    created_at: datetime


class ReindexResponse(BaseModel):
    """知识库重建接口返回结果。"""

    collection_name: str
    inserted_count: int


class MemoryRebuildResponse(BaseModel):
    """从 MySQL 回放会话后返回给前端的摘要信息。"""

    session_id: str
    memory_source: str
    summary: str
    slots: dict = Field(default_factory=dict)
    intent: str | None = None

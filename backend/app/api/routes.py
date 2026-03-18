"""FastAPI 路由定义。

这一层负责：
1. 协议层的数据校验和返回结构
2. 登录态恢复
3. 把业务调用委托给 workflow、repository 和 service
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import User
from app.repositories.store import ShopRepository
from app.schemas.auth import AuthEnvelope, LoginRequest, RegisterRequest, UserPayload
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MemoryRebuildResponse,
    ReindexResponse,
    SessionResponse,
    SessionSummary,
    TicketItem,
)


router = APIRouter()


def get_container(request: Request):
    """从 FastAPI 应用状态中取出服务容器。"""
    return request.app.state.container


def to_user_payload(user: User) -> UserPayload:
    """把 ORM 用户对象转换成对外响应结构。"""
    return UserPayload(id=user.id, email=user.email, display_name=user.display_name)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    container=Depends(get_container),
) -> User:
    """依赖注入：恢复当前登录用户。"""
    repo = ShopRepository(db)
    return container.auth_service.get_current_user(request, repo)


@router.get("/health")
def healthcheck() -> dict:
    """最基础的服务健康检查。"""
    return {"status": "ok"}


@router.post("/auth/register", response_model=AuthEnvelope, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    container=Depends(get_container),
) -> AuthEnvelope:
    """注册新用户，并自动写入登录 Cookie。"""
    repo = ShopRepository(db)
    email = payload.email.strip().lower()
    if repo.get_user_by_email(email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = repo.create_user(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=container.auth_service.hash_password(payload.password),
    )
    db.commit()

    token = container.auth_service.create_access_token(user.id)
    container.auth_service.set_auth_cookie(response, token)
    return AuthEnvelope(user=to_user_payload(user))


@router.post("/auth/login", response_model=AuthEnvelope)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    container=Depends(get_container),
) -> AuthEnvelope:
    """校验邮箱密码并写入登录 Cookie。"""
    repo = ShopRepository(db)
    email = payload.email.strip().lower()
    user = repo.get_user_by_email(email)
    if not user or not container.auth_service.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = container.auth_service.create_access_token(user.id)
    container.auth_service.set_auth_cookie(response, token)
    return AuthEnvelope(user=to_user_payload(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(container=Depends(get_container)) -> Response:
    """清理登录 Cookie。"""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    container.auth_service.clear_auth_cookie(response)
    return response


@router.get("/auth/me", response_model=AuthEnvelope)
def get_me(current_user: User = Depends(get_current_user)) -> AuthEnvelope:
    """返回当前登录用户。"""
    return AuthEnvelope(user=to_user_payload(current_user))


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionSummary]:
    """列出当前用户最近活跃的会话。"""
    repo = ShopRepository(db)
    sessions = repo.list_sessions_for_user(current_user.id)
    return [
        SessionSummary(
            session_id=item.session_id,
            title=item.title,
            current_intent=item.current_intent,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in sessions
    ]


@router.post("/sessions", response_model=SessionSummary, status_code=status.HTTP_201_CREATED)
def create_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionSummary:
    """创建一个空会话，供前端“新对话”按钮直接使用。"""
    repo = ShopRepository(db)
    session = repo.create_session(current_user.id)
    db.commit()
    return SessionSummary(
        session_id=session.session_id,
        title=session.title,
        current_intent=session.current_intent,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    container=Depends(get_container),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """执行一轮完整的客服 Agent 对话。"""
    repo = ShopRepository(db)
    if payload.session_id and not repo.get_session_for_user(payload.session_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = container.workflow.invoke(
        user_id=current_user.id,
        message=payload.message,
        db=db,
        session_id=payload.session_id,
    )
    return ChatResponse(
        session_id=result["session_id"],
        reply=result["final_reply"],
        intent=result.get("intent", "general"),
        citations=result.get("citations", []),
        used_tools=result.get("used_tools", []),
        action="handoff" if result.get("needs_handoff") else "reply",
        memory_source=result.get("memory_source", "new"),
        needs_handoff=result.get("needs_handoff", False),
        handoff_ticket_id=result.get("handoff_ticket_id"),
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """查看当前用户某个会话的消息历史和状态快照。"""
    repo = ShopRepository(db)
    session = repo.get_session_for_user(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = repo.list_session_messages(session_id)
    snapshots = repo.list_snapshots(session_id)
    return SessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        current_intent=session.current_intent,
        messages=[
            {
                "role": item.role,
                "content": item.content,
                "intent": item.intent,
                "citations": item.citations_json,
                "tool_calls": item.tool_calls_json,
                "created_at": item.created_at,
            }
            for item in messages
        ],
        snapshots=[
            {
                "intent": item.intent,
                "memory_source": item.memory_source,
                "state": item.state_json,
                "created_at": item.created_at,
            }
            for item in snapshots
        ],
    )


@router.get("/tickets", response_model=list[TicketItem])
def list_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TicketItem]:
    """返回当前用户的人工转接工单。"""
    repo = ShopRepository(db)
    tickets = repo.list_tickets_for_user(current_user.id)
    return [
        TicketItem(
            ticket_no=item.ticket_no,
            session_id=item.session_id,
            user_id=item.user_id,
            reason=item.reason,
            status=item.status,
            summary=item.summary,
            created_at=item.created_at,
        )
        for item in tickets
    ]


@router.post("/knowledge/reindex", response_model=ReindexResponse)
def reindex_knowledge(
    db: Session = Depends(get_db),
    container=Depends(get_container),
    current_user: User = Depends(get_current_user),
) -> ReindexResponse:
    """重建 Milvus 知识库索引。"""
    del current_user
    repo = ShopRepository(db)
    inserted_count = container.bootstrap_service.reindex_knowledge(repo)
    return ReindexResponse(collection_name=container.settings.milvus_collection, inserted_count=inserted_count)


@router.post("/memory/rebuild/{session_id}", response_model=MemoryRebuildResponse)
def rebuild_memory(
    session_id: str,
    db: Session = Depends(get_db),
    container=Depends(get_container),
    current_user: User = Depends(get_current_user),
) -> MemoryRebuildResponse:
    """清空或丢失 Redis 后，从 MySQL 快照恢复当前用户的会话短期记忆。"""
    repo = ShopRepository(db)
    if not repo.get_session_for_user(session_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    state = container.memory_service.rebuild(session_id, repo)
    return MemoryRebuildResponse(
        session_id=session_id,
        memory_source=state.get("memory_source", "mysql_rebuild"),
        summary=state.get("summary", ""),
        slots=state.get("slots", {}),
        intent=state.get("intent"),
    )

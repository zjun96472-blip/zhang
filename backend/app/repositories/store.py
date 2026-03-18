"""数据库仓储层。

这一层把常用的 CRUD 和查询逻辑集中起来，避免 workflow 直接拼 SQL。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from app.data.seed_data import ORDERS, PRODUCTS, USERS
from app.models.entities import ChatMessage, ChatSession, HandoffTicket, Order, Product, SessionStateSnapshot, User


def _utcnow() -> datetime:
    """生成去掉时区信息的 UTC 时间。"""
    return datetime.now(UTC).replace(tzinfo=None)


class ShopRepository:
    """封装 ShopMate 业务对象的数据库访问逻辑。"""

    def __init__(self, db: Session):
        self.db = db

    def seed_sample_data(self, password_hasher: Callable[[str], str]) -> None:
        """在空数据库中初始化演示用户、样例商品和订单。"""
        user_count = self.db.scalar(select(func.count(User.id)))
        if not user_count:
            for item in USERS:
                self.db.add(
                    User(
                        id=item["id"],
                        email=item["email"],
                        display_name=item["display_name"],
                        password_hash=password_hasher(item["password"]),
                    )
                )

        product_count = self.db.scalar(select(func.count(Product.id)))
        if not product_count:
            for product in PRODUCTS:
                self.db.add(Product(**product))

        order_count = self.db.scalar(select(func.count(Order.id)))
        if not order_count:
            for order in ORDERS:
                self.db.add(Order(**order))

        self.db.commit()

    def list_products(self) -> list[Product]:
        """返回全部商品，主要供知识库构建使用。"""
        return list(self.db.scalars(select(Product).order_by(Product.name)).all())

    def search_products(self, keyword: str) -> list[Product]:
        """按商品名模糊搜索。"""
        query = select(Product).where(Product.name.ilike(f"%{keyword}%")).order_by(Product.name)
        return list(self.db.scalars(query).all())

    def get_product_names(self) -> list[str]:
        """只取商品名列表，便于做轻量级命中判断。"""
        return [item.name for item in self.list_products()]

    def get_user_by_email(self, email: str) -> User | None:
        """按邮箱读取用户。"""
        return self.db.scalar(select(User).where(User.email == email))

    def get_user_by_id(self, user_id: str) -> User | None:
        """按主键读取用户。"""
        return self.db.scalar(select(User).where(User.id == user_id))

    def create_user(self, email: str, display_name: str, password_hash: str) -> User:
        """创建一个新用户。"""
        user = User(
            id=f"user-{uuid4().hex[:12]}",
            email=email,
            display_name=display_name,
            password_hash=password_hash,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def get_order_by_id(self, order_id: str, user_id: str | None = None) -> Order | None:
        """查询订单，可选按用户过滤，避免串单。"""
        query: Select = select(Order).where(Order.order_id == order_id)
        if user_id:
            query = query.where(Order.user_id == user_id)
        return self.db.scalar(query)

    def create_session(self, user_id: str, title: str = "新对话") -> ChatSession:
        """为当前用户创建一个空会话。"""
        session = ChatSession(session_id=uuid4().hex, user_id=user_id, title=title)
        self.db.add(session)
        self.db.flush()
        return session

    def get_or_create_session(self, session_id: str, user_id: str, first_message: str) -> ChatSession:
        """查找已有会话；如果不存在则创建。"""
        session = self.db.scalar(select(ChatSession).where(ChatSession.session_id == session_id))
        if session:
            if session.user_id != user_id:
                raise ValueError("Session does not belong to current user")
            session.updated_at = _utcnow()
            if not session.title or session.title == "新对话":
                session.title = first_message[:40]
            self.db.add(session)
            self.db.flush()
            return session

        session = ChatSession(session_id=session_id, user_id=user_id, title=first_message[:40] or "新对话")
        self.db.add(session)
        self.db.flush()
        return session

    def update_session_intent(self, session_id: str, intent: str) -> None:
        """更新会话当前意图，方便列表页快速查看。"""
        session = self.db.scalar(select(ChatSession).where(ChatSession.session_id == session_id))
        if session:
            session.current_intent = intent
            session.updated_at = _utcnow()
            self.db.add(session)
            self.db.flush()

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        citations: list | None = None,
        tool_calls: list | None = None,
    ) -> ChatMessage:
        """向会话中追加一条消息。"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            citations_json=citations or [],
            tool_calls_json=tool_calls or [],
        )
        self.db.add(message)
        self.db.flush()
        return message

    def save_snapshot(self, session_id: str, intent: str | None, memory_source: str, state: dict) -> SessionStateSnapshot:
        """持久化运行时状态快照。"""
        snapshot = SessionStateSnapshot(
            session_id=session_id,
            intent=intent,
            memory_source=memory_source,
            state_json=state,
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def list_session_messages(self, session_id: str, limit: int | None = None) -> list[ChatMessage]:
        """按时间正序返回会话消息。"""
        query = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        if limit:
            query = query.limit(limit)
        return list(self.db.scalars(query).all())

    def list_recent_messages(self, session_id: str, limit: int = 10) -> list[ChatMessage]:
        """返回最近 N 条消息，并重新转回正序。"""
        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        messages = list(self.db.scalars(query).all())
        return list(reversed(messages))

    def get_latest_snapshot(self, session_id: str) -> SessionStateSnapshot | None:
        """获取最新状态快照，供 Redis 回放失败时重建上下文。"""
        query = (
            select(SessionStateSnapshot)
            .where(SessionStateSnapshot.session_id == session_id)
            .order_by(desc(SessionStateSnapshot.created_at))
        )
        return self.db.scalar(query)

    def get_session(self, session_id: str) -> ChatSession | None:
        """根据 session_id 读取会话。"""
        return self.db.scalar(select(ChatSession).where(ChatSession.session_id == session_id))

    def get_session_for_user(self, session_id: str, user_id: str) -> ChatSession | None:
        """根据 session_id 和用户读取会话，避免跨用户访问。"""
        return self.db.scalar(
            select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
        )

    def list_sessions_for_user(self, user_id: str, limit: int = 50) -> list[ChatSession]:
        """返回当前用户最近活跃的会话列表。"""
        query = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at), desc(ChatSession.created_at))
            .limit(limit)
        )
        return list(self.db.scalars(query).all())

    def list_snapshots(self, session_id: str, limit: int = 10) -> list[SessionStateSnapshot]:
        """返回最近若干个快照，供调试页展示。"""
        query = (
            select(SessionStateSnapshot)
            .where(SessionStateSnapshot.session_id == session_id)
            .order_by(desc(SessionStateSnapshot.created_at))
            .limit(limit)
        )
        return list(reversed(self.db.scalars(query).all()))

    def create_ticket(self, session_id: str, user_id: str, reason: str, summary: str) -> HandoffTicket:
        """创建人工工单。"""
        ticket = HandoffTicket(
            ticket_no=f"TK-{uuid4().hex[:8].upper()}",
            session_id=session_id,
            user_id=user_id,
            reason=reason,
            summary=summary,
        )
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def list_tickets_for_user(self, user_id: str) -> list[HandoffTicket]:
        """按创建时间倒序返回当前用户的工单列表。"""
        query = select(HandoffTicket).where(HandoffTicket.user_id == user_id).order_by(desc(HandoffTicket.created_at))
        return list(self.db.scalars(query).all())

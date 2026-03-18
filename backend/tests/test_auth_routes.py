"""认证与会话接口的集成测试。"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import Base, get_db
from app.repositories.store import ShopRepository
from app.services.auth import AuthService


class FakeWorkflow:
    """用来验证路由是否把当前登录用户传进 workflow。"""

    def __init__(self):
        self.last_invoke: dict | None = None

    def invoke(self, user_id: str, message: str, db, session_id: str | None = None) -> dict:
        self.last_invoke = {
            "user_id": user_id,
            "message": message,
            "session_id": session_id,
        }
        return {
            "session_id": session_id or "generated-session",
            "final_reply": f"reply:{message}",
            "intent": "general",
            "citations": [],
            "used_tools": [],
            "memory_source": "new",
            "needs_handoff": False,
        }


class FakeMemoryService:
    """测试用记忆服务。"""

    def rebuild(self, session_id: str, repo: ShopRepository) -> dict:
        del repo
        return {
            "session_id": session_id,
            "memory_source": "mysql_rebuild",
            "summary": "rebuild",
            "slots": {},
            "intent": "general",
        }


class FakeBootstrapService:
    """测试用知识库服务。"""

    def reindex_knowledge(self, repo: ShopRepository) -> int:
        del repo
        return 0


def build_client() -> tuple[TestClient, sessionmaker, SimpleNamespace]:
    """构造一个带内存数据库的测试应用。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    settings = get_settings()
    auth_service = AuthService(settings)
    workflow = FakeWorkflow()
    container = SimpleNamespace(
        settings=settings,
        auth_service=auth_service,
        workflow=workflow,
        memory_service=FakeMemoryService(),
        bootstrap_service=FakeBootstrapService(),
    )

    with TestingSessionLocal() as db:
        repo = ShopRepository(db)
        repo.seed_sample_data(auth_service.hash_password)

    app = FastAPI()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.container = container
    app.include_router(router, prefix="/api")
    return TestClient(app), TestingSessionLocal, container


def login_demo_user(client: TestClient) -> None:
    """登录默认演示账号。"""
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@shopmate.local", "password": "demo123456"},
    )
    assert response.status_code == 200


def test_register_and_me_flow():
    """新用户注册后应自动处于登录状态。"""
    client, _, _ = build_client()

    response = client.post(
        "/api/auth/register",
        json={"email": "new-user@example.com", "password": "password123", "display_name": "新用户"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "new-user@example.com"

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["display_name"] == "新用户"


def test_login_logout_and_protected_routes():
    """未登录应 401，登录后可访问，退出后再次 401。"""
    client, _, _ = build_client()

    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/tickets").status_code == 401
    assert client.post("/api/chat", json={"message": "你好"}).status_code == 401

    login_demo_user(client)
    assert client.get("/api/auth/me").status_code == 200

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_sessions_and_tickets_are_filtered_by_current_user():
    """当前用户只能看到自己的会话和工单。"""
    client, session_local, _ = build_client()

    with session_local() as db:
        repo = ShopRepository(db)
        demo_session = repo.create_session("demo-user", title="演示用户会话")
        campus_session = repo.create_session("campus-user", title="校园用户会话")
        repo.create_ticket(demo_session.session_id, "demo-user", "测试", "demo ticket")
        repo.create_ticket(campus_session.session_id, "campus-user", "测试", "campus ticket")
        db.commit()

    login_demo_user(client)

    sessions_response = client.get("/api/sessions")
    assert sessions_response.status_code == 200
    session_titles = [item["title"] for item in sessions_response.json()]
    assert "演示用户会话" in session_titles
    assert "校园用户会话" not in session_titles

    tickets_response = client.get("/api/tickets")
    assert tickets_response.status_code == 200
    assert len(tickets_response.json()) == 1
    assert tickets_response.json()[0]["user_id"] == "demo-user"

    forbidden_session = client.get(f"/api/sessions/{campus_session.session_id}")
    assert forbidden_session.status_code == 404


def test_chat_uses_authenticated_user_and_existing_session():
    """聊天接口不再信任前端传 user_id，而是使用当前登录用户。"""
    client, session_local, container = build_client()

    with session_local() as db:
        repo = ShopRepository(db)
        session = repo.create_session("demo-user", title="测试会话")
        db.commit()
        session_id = session.session_id

    login_demo_user(client)

    response = client.post("/api/chat", json={"session_id": session_id, "message": "帮我查物流"})
    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
    assert container.workflow.last_invoke["user_id"] == "demo-user"
    assert container.workflow.last_invoke["session_id"] == session_id

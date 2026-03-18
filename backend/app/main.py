"""FastAPI 应用入口。

这里负责拼装所有服务对象，并在应用启动时准备数据库表、
样例数据与知识库索引。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import Base, SessionLocal, engine
from app.graph.workflow import ShopMateWorkflow
from app.repositories.store import ShopRepository
from app.services.auth import AuthService
from app.services.bootstrap import BootstrapService
from app.services.llm import AgentBrain
from app.services.memory import MemoryService
from app.services.milvus_store import MilvusKnowledgeBase


class ServiceContainer:
    """集中持有运行期依赖，避免在请求过程中重复初始化重量级对象。"""

    def __init__(self):
        self.settings = get_settings()
        self.auth_service = AuthService(self.settings)
        self.brain = AgentBrain(self.settings)
        self.memory_service = MemoryService(self.settings)
        self.knowledge_base = MilvusKnowledgeBase(self.settings, self.brain)
        self.bootstrap_service = BootstrapService(self.knowledge_base)
        self.workflow = ShopMateWorkflow(self.brain, self.memory_service, self.bootstrap_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期钩子。

    启动时创建表、准备样例数据，并尝试自动构建 Milvus 索引。
    如果索引构建失败，不阻止服务启动，方便在基础设施未就绪时继续调试。
    """

    Base.metadata.create_all(bind=engine)
    container = ServiceContainer()
    with SessionLocal() as db:
        repo = ShopRepository(db)
        repo.seed_sample_data(container.auth_service.hash_password)
        try:
            container.bootstrap_service.reindex_knowledge(repo)
        except Exception:
            db.rollback()
        else:
            db.commit()
    app.state.container = container
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)

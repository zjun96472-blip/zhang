"""Milvus 知识库存取层。"""

from __future__ import annotations

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.core.config import Settings
from app.services.llm import AgentBrain


class MilvusKnowledgeBase:
    """封装 Milvus 连接、建表、写入和检索逻辑。"""

    def __init__(self, settings: Settings, brain: AgentBrain):
        self.settings = settings
        self.brain = brain
        self.collection_name = settings.milvus_collection

    def connect(self) -> None:
        """建立到 Milvus 的默认连接。"""
        connections.connect(
            alias="default",
            uri=self.settings.milvus_uri,
            token=self.settings.milvus_token or None,
        )

    def ensure_collection(self) -> Collection:
        """确保知识库 collection 存在，不存在则自动创建。"""
        self.connect()
        if utility.has_collection(self.collection_name):
            collection = Collection(self.collection_name)
            collection.load()
            return collection

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=128, is_primary=True, auto_id=False),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.settings.embedding_dimensions),
        ]
        schema = CollectionSchema(fields=fields, description="ShopMate knowledge base")
        collection = Collection(name=self.collection_name, schema=schema)
        collection.create_index(
            field_name="vector",
            index_params={"index_type": "AUTOINDEX", "metric_type": "COSINE", "params": {}},
        )
        collection.load()
        return collection

    def recreate_collection(self, documents: list[dict]) -> int:
        """删除旧 collection 并重建索引。"""
        self.connect()
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
        collection = self.ensure_collection()
        embeddings = self.brain.embed_documents([doc["content"] for doc in documents])
        collection.insert(
            [
                [doc["id"] for doc in documents],
                [doc["content"] for doc in documents],
                [doc["doc_type"] for doc in documents],
                [doc["source"] for doc in documents],
                [doc["category"] for doc in documents],
                embeddings,
            ]
        )
        collection.flush()
        collection.load()
        return len(documents)

    def search(self, query: str, top_k: int = 4, doc_types: list[str] | None = None) -> list[dict]:
        """检索最相关的知识库文档。"""
        collection = self.ensure_collection()
        expr = None
        if doc_types:
            formatted = ",".join([f'"{item}"' for item in doc_types])
            expr = f"doc_type in [{formatted}]"
        try:
            results = collection.search(
                data=[self.brain.embed_query(query)],
                anns_field="vector",
                param={"metric_type": "COSINE", "params": {}},
                limit=top_k,
                output_fields=["id", "content", "doc_type", "source", "category"],
                expr=expr,
            )
        except Exception:
            # 检索失败时返回空结果，让上游继续走兜底回复而不是直接报错。
            return []

        hits = []
        for item in results[0]:
            entity = item.entity
            hits.append(
                {
                    "id": entity.get("id"),
                    "content": entity.get("content"),
                    "doc_type": entity.get("doc_type"),
                    "source": entity.get("source"),
                    "category": entity.get("category"),
                    "score": float(item.score),
                }
            )
        return hits

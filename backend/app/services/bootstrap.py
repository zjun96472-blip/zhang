"""启动阶段的准备逻辑。

这个服务负责把数据库里的商品数据和静态 FAQ/政策文档合并，
最终统一送入 Milvus 进行索引。
"""

from __future__ import annotations

from app.data.seed_data import FAQ_DOCS, POLICY_DOCS
from app.models.entities import Product
from app.repositories.store import ShopRepository
from app.services.milvus_store import MilvusKnowledgeBase


class BootstrapService:
    """负责知识库初始化与重建。"""

    def __init__(self, knowledge_base: MilvusKnowledgeBase):
        self.knowledge_base = knowledge_base

    def build_knowledge_documents(self, repo: ShopRepository) -> list[dict]:
        """把商品、FAQ、政策统一转换成 Milvus 文档结构。"""
        products = repo.list_products()
        product_docs = [self._product_to_doc(product) for product in products]
        return product_docs + FAQ_DOCS + POLICY_DOCS

    def reindex_knowledge(self, repo: ShopRepository) -> int:
        """重建整套知识库索引。"""
        documents = self.build_knowledge_documents(repo)
        return self.knowledge_base.recreate_collection(documents)

    @staticmethod
    def _product_to_doc(product: Product) -> dict:
        """把一条商品记录转换为适合向量检索的描述文本。"""
        content = (
            f"{product.name}，售价 {product.price} 元，卖点：{product.highlights}。"
            f"规格：{product.specs}。适合人群：{product.audience}。"
        )
        return {
            "id": f"product-{product.product_code}",
            "content": content,
            "doc_type": "product",
            "source": f"商品库/{product.name}",
            "category": product.category,
        }

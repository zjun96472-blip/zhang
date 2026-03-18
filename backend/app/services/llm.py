"""大模型与向量模型访问层。

这个模块同时支持两种运行模式：
1. 真实百炼 OpenAI-compatible 接口
2. 无密钥场景下的 mock 模式，方便本地演示和测试
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import Settings
from app.services.heuristics import extract_order_id, infer_intent


class AgentBrain:
    """封装 LLM 和 Embedding 的统一调用入口。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        # 没有密钥时自动退化为 mock 模式，保证项目在演示环境中也能跑通。
        self.mock_mode = settings.use_mock_llm or not settings.dashscope_api_key
        self.chat_model = None
        if not self.mock_mode:
            self.chat_model = ChatOpenAI(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
                model=settings.llm_model,
                temperature=0.2,
                max_retries=2,
            )

        self.embedding_model = OpenAIEmbeddings(
            api_key=settings.dashscope_api_key or "mock-key",
            base_url=settings.dashscope_base_url,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量生成文档向量。"""
        if self.mock_mode:
            return [self._fake_vector(text) for text in texts]
        return self.embedding_model.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """生成查询向量。"""
        if self.mock_mode:
            return self._fake_vector(text)
        return self.embedding_model.embed_query(text)

    def route_intent(self, message: str, slots: dict[str, Any]) -> dict[str, Any]:
        """用大模型或启发式规则识别用户意图。"""
        fallback_intent, fallback_confidence = infer_intent(message)
        fallback = {
            "intent": fallback_intent,
            "confidence": fallback_confidence,
            "order_id": extract_order_id(message) or slots.get("order_id"),
        }
        if self.mock_mode:
            return fallback

        prompt = """
你是电商客服 Agent 的意图路由器。请输出 JSON，字段必须只有:
intent, confidence, order_id

intent 只能从以下值里选择:
- product_consultation
- logistics_query
- return_refund
- promotion_policy
- complaint_handoff
- general

confidence 取 0 到 1 之间的小数。
如果消息里没有订单号则 order_id 设为 null。
只输出 JSON，不要补充解释。
"""
        content = self._invoke_json(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=f"历史槽位: {json.dumps(slots, ensure_ascii=False)}\n用户消息: {message}"),
            ],
            fallback,
        )
        content["intent"] = content.get("intent", fallback_intent)
        content["confidence"] = float(content.get("confidence", fallback_confidence))
        content["order_id"] = content.get("order_id") or fallback["order_id"]
        return content

    def generate_reply(self, payload: dict[str, Any]) -> str:
        """基于当前事实生成客服回复。"""
        if self.mock_mode:
            return self._fallback_reply(payload)

        system_prompt = """
你是 ShopMate 电商客服助手。请根据给定事实作答：
1. 只能使用提供的订单、政策和知识库事实。
2. 如果信息不足，不要编造。
3. 涉及赔付、补偿、严重投诉时，明确说明需要转人工。
4. 回复用自然、稳健、简洁的中文。
"""
        context = json.dumps(payload, ensure_ascii=False, default=str)
        message = self.chat_model.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=f"请基于以下事实回复用户:\n{context}")]
        )
        return str(message.content).strip()

    def summarize_turn(self, payload: dict[str, Any]) -> str:
        """把一轮对话压缩成短摘要，供 Redis 记忆缓存使用。"""
        if self.mock_mode:
            intent = payload.get("intent", "general")
            order_id = payload.get("slots", {}).get("order_id")
            summary = f"意图={intent}"
            if order_id:
                summary += f"，订单={order_id}"
            return summary

        prompt = """
请把这轮客服对话总结成一句中文短句，用于 Redis 会话摘要缓存。
保留意图、订单号和待处理动作。只输出一句话。
"""
        response = self.chat_model.invoke(
            [SystemMessage(content=prompt), HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str))]
        )
        return str(response.content).strip()

    def summarize_handoff(self, payload: dict[str, Any]) -> str:
        """把当前上下文整理成可读的人工工单摘要。"""
        if self.mock_mode:
            return f"用户 {payload['user_id']} 触发人工转接，原因：{payload['reason']}。最近消息：{payload['message']}"

        prompt = """
请将以下客服上下文整理成一段人工客服可直接阅读的摘要。
要求包含：用户诉求、订单号（如有）、当前系统判断、需要人工跟进的原因。
用中文输出 2 到 4 句。
"""
        response = self.chat_model.invoke(
            [SystemMessage(content=prompt), HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str))]
        )
        return str(response.content).strip()

    def _invoke_json(self, messages: list, fallback: dict[str, Any]) -> dict[str, Any]:
        """调用模型并尝试把回复解析成 JSON。"""
        try:
            response = self.chat_model.invoke(messages)
            return self._load_json(str(response.content))
        except Exception:
            return fallback

    @staticmethod
    def _load_json(text: str) -> dict[str, Any]:
        """从模型回复中提取 JSON 主体。

        有些模型会带 Markdown 代码块，因此这里做一层宽松清洗。
        """

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.split("\n", 1)[-1]
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end >= start:
            cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)

    def _fallback_reply(self, payload: dict[str, Any]) -> str:
        """mock 模式下的规则回复。"""
        intent = payload.get("intent")
        user_message = payload.get("user_message", "")
        if payload.get("missing_fields"):
            return "为了继续帮你处理，我还需要你的订单号。格式一般像 ORD-10001。"
        if intent == "product_consultation":
            docs = payload.get("retrieved_docs", [])
            if docs:
                lines = [f"我帮你查到了这些重点：{docs[0]['content']}"]
                if len(docs) > 1:
                    lines.append(f"补充信息：{docs[1]['content']}")
                return "\n".join(lines)
            return "我可以继续帮你做商品对比。你也可以告诉我具体商品名，我会结合知识库给你建议。"
        if intent == "logistics_query":
            order = payload.get("order_context")
            if order:
                return f"订单 {order['order_id']} 当前物流状态是 {order['logistics_status']}，运单号为 {order['tracking_no']}。"
            return "我暂时没有查到对应订单，请确认订单号是否正确。"
        if intent == "return_refund":
            policy = payload.get("policy_result") or {}
            return f"{policy.get('reason', '我先帮你看了退换货条件。')} {policy.get('next_step', '')}".strip()
        if intent == "promotion_policy":
            docs = payload.get("retrieved_docs", [])
            if docs:
                return docs[0]["content"]
            return "优惠券和平台红包通常可以叠加，具体还是以结算页为准。"
        if payload.get("needs_handoff"):
            return "这个问题需要人工客服进一步处理，我已经帮你记录并转接。"
        return f"我已经收到你的问题：{user_message}。如果你告诉我商品名或订单号，我可以继续深入帮你查。"

    def _fake_vector(self, text: str) -> list[float]:
        """生成一个稳定的伪向量，用于无模型环境下的演示。"""
        values = [0.0] * self.settings.embedding_dimensions
        for index, char in enumerate(text[: self.settings.embedding_dimensions]):
            values[index] = (ord(char) % 97) / 100.0
        return values

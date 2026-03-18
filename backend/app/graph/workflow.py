"""ShopMate 的 LangGraph 主工作流。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.graph.state import AgentState
from app.repositories.store import ShopRepository
from app.services.bootstrap import BootstrapService
from app.services.heuristics import extract_compensation_risk, extract_order_id, normalize_product_keyword
from app.services.llm import AgentBrain
from app.services.memory import MemoryService
from app.services.policy import evaluate_return_policy


class ShopMateWorkflow:
    """把客服 Agent 的每个步骤编排成一个清晰可追踪的有向图。"""

    def __init__(
        self,
        brain: AgentBrain,
        memory_service: MemoryService,
        bootstrap_service: BootstrapService,
    ):
        self.brain = brain
        self.memory_service = memory_service
        self.bootstrap_service = bootstrap_service
        self.graph = self._build_graph()

    def invoke(self, user_id: str, message: str, db, session_id: str | None = None) -> dict:
        """执行一轮完整的客服对话。"""
        initial_state: AgentState = {
            "session_id": session_id or uuid4().hex,
            "user_id": user_id,
            "user_message": message,
            "messages": [],
            "slots": {},
            "db": db,
            "used_tools": [],
            "citations": [],
            "needs_handoff": False,
        }
        return self.graph.invoke(initial_state)

    def _build_graph(self):
        """定义图节点和边。"""
        graph = StateGraph(AgentState)
        graph.add_node("load_memory", self.load_memory)
        graph.add_node("intent_router", self.intent_router)
        graph.add_node("collect_missing_info", self.collect_missing_info)
        graph.add_node("retrieve_from_milvus", self.retrieve_from_milvus)
        graph.add_node("query_order_tool", self.query_order_tool)
        graph.add_node("policy_checker", self.policy_checker)
        graph.add_node("response_generator", self.response_generator)
        graph.add_node("risk_guard", self.risk_guard)
        graph.add_node("persist_memory", self.persist_memory)
        graph.add_node("handoff_ticket", self.handoff_ticket)

        graph.set_entry_point("load_memory")
        graph.add_edge("load_memory", "intent_router")
        graph.add_conditional_edges(
            "intent_router",
            self._route_after_intent,
            {
                "collect_missing_info": "collect_missing_info",
                "retrieve_from_milvus": "retrieve_from_milvus",
                "query_order_tool": "query_order_tool",
                "response_generator": "response_generator",
            },
        )
        graph.add_edge("collect_missing_info", "persist_memory")
        graph.add_edge("retrieve_from_milvus", "response_generator")
        graph.add_conditional_edges(
            "query_order_tool",
            self._route_after_order_lookup,
            {"policy_checker": "policy_checker", "response_generator": "response_generator"},
        )
        graph.add_edge("policy_checker", "response_generator")
        graph.add_edge("response_generator", "risk_guard")
        graph.add_edge("risk_guard", "persist_memory")
        graph.add_conditional_edges(
            "persist_memory",
            self._route_after_persist,
            {"handoff_ticket": "handoff_ticket", "end": END},
        )
        graph.add_edge("handoff_ticket", END)
        return graph.compile()

    def load_memory(self, state: AgentState) -> dict:
        """在处理用户消息前先加载上一轮上下文。"""
        repo = ShopRepository(state["db"])
        memory_state = self.memory_service.load_runtime_state(state["session_id"], repo)
        return {
            "messages": memory_state.get("messages", []),
            "slots": memory_state.get("slots", {}),
            "summary": memory_state.get("summary", ""),
            "intent": memory_state.get("intent"),
            "memory_source": memory_state.get("memory_source", "new"),
        }

    def intent_router(self, state: AgentState) -> dict:
        """识别意图，并尽可能从本轮消息中补齐槽位。"""
        current_slots = dict(state.get("slots", {}))
        explicit_order_id = extract_order_id(state["user_message"])
        if explicit_order_id:
            current_slots["order_id"] = explicit_order_id

        route = self.brain.route_intent(state["user_message"], current_slots)
        if route.get("order_id"):
            current_slots["order_id"] = route["order_id"]

        missing_fields = []
        if route["intent"] in {"logistics_query", "return_refund"} and not current_slots.get("order_id"):
            missing_fields.append("order_id")

        return {
            "intent": route["intent"],
            "confidence": route["confidence"],
            "slots": current_slots,
            "missing_fields": missing_fields,
        }

    def collect_missing_info(self, state: AgentState) -> dict:
        """订单类问题缺少订单号时，先向用户追问。"""
        return {
            "final_reply": "为了继续帮你查物流或售后进度，我还需要订单号。格式一般像 ORD-10001。",
            "summary": f"追问缺失字段: {','.join(state.get('missing_fields', []))}",
        }

    def retrieve_from_milvus(self, state: AgentState) -> dict:
        """执行知识库检索，并把结果转换为前端可展示的引用信息。"""
        repo = ShopRepository(state["db"])
        docs = self.bootstrap_service.knowledge_base.search(
            query=state["user_message"],
            top_k=4,
            doc_types=["product", "faq", "policy"],
        )
        used_tools = list(state.get("used_tools", []))
        citations = [
            {
                "id": doc["id"],
                "source": doc["source"],
                "doc_type": doc["doc_type"],
                "category": doc["category"],
                "score": round(doc["score"], 4),
            }
            for doc in docs
        ]

        # 如果用户已经明确提到商品名，就顺带把商品名写入 slots，方便后续多轮追问。
        product_names = repo.get_product_names()
        keyword = normalize_product_keyword(state["user_message"], product_names)
        if keyword:
            products = repo.search_products(keyword)
            if products:
                used_tools.append("search_products")
                state["slots"]["product_name"] = products[0].name

        return {"retrieved_docs": docs, "used_tools": used_tools, "citations": citations}

    def query_order_tool(self, state: AgentState) -> dict:
        """读取订单信息，供物流查询或售后规则判断使用。"""
        repo = ShopRepository(state["db"])
        order_id = state.get("slots", {}).get("order_id")
        order = repo.get_order_by_id(order_id, state["user_id"]) if order_id else None
        payload = None
        if order:
            payload = {
                "order_id": order.order_id,
                "user_id": order.user_id,
                "product_code": order.product_code,
                "status": order.status,
                "logistics_status": order.logistics_status,
                "tracking_no": order.tracking_no,
                "refund_status": order.refund_status,
                "ordered_at": order.ordered_at,
                "delivered_at": order.delivered_at,
                "metadata": order.metadata_json,
                "product_name": order.product.name,
            }
        used_tools = list(state.get("used_tools", []))
        used_tools.append("get_order_detail")
        return {"order_context": payload, "used_tools": used_tools}

    def policy_checker(self, state: AgentState) -> dict:
        """根据订单状态判断退货是否满足规则。"""
        policy_result = evaluate_return_policy(
            state.get("order_context"),
            now=datetime.now(UTC).replace(tzinfo=None),
        )
        citations = list(state.get("citations", []))
        citations.append(
            {
                "id": "policy-checker",
                "source": policy_result["policy_source"],
                "doc_type": "policy",
                "category": "return",
                "score": None,
            }
        )
        return {"policy_result": policy_result, "citations": citations}

    def response_generator(self, state: AgentState) -> dict:
        """把当前事实上下文交给 LLM 组织最终回复。"""
        reply = self.brain.generate_reply(
            {
                "intent": state.get("intent"),
                "user_message": state["user_message"],
                "history": state.get("messages", []),
                "slots": state.get("slots", {}),
                "retrieved_docs": state.get("retrieved_docs", []),
                "order_context": state.get("order_context"),
                "policy_result": state.get("policy_result"),
                "citations": state.get("citations", []),
                "needs_handoff": state.get("needs_handoff", False),
            }
        )
        return {"final_reply": reply}

    def risk_guard(self, state: AgentState) -> dict:
        """对高风险场景做统一兜底。"""
        needs_handoff = state.get("intent") == "complaint_handoff"
        reason = None
        if extract_compensation_risk(state["user_message"]):
            needs_handoff = True
            reason = "赔付/投诉风险"
        elif state.get("confidence", 1.0) < 0.55:
            needs_handoff = True
            reason = "低置信度"
        elif state.get("intent") == "return_refund" and state.get("policy_result", {}).get("eligible") is False:
            reason = "售后争议需人工兜底"

        final_reply = state.get("final_reply", "")
        if needs_handoff and "人工" not in final_reply:
            final_reply = f"{final_reply}\n\n这个问题我已经为你转给人工客服继续跟进。"

        summary = self.brain.summarize_turn(
            {
                "intent": state.get("intent"),
                "user_message": state["user_message"],
                "reply": final_reply,
                "slots": state.get("slots", {}),
                "used_tools": state.get("used_tools", []),
            }
        )
        return {"needs_handoff": needs_handoff, "handoff_reason": reason, "final_reply": final_reply, "summary": summary}

    def persist_memory(self, state: AgentState) -> dict:
        """把本轮对话结果写回 MySQL 和 Redis。"""
        repo = ShopRepository(state["db"])
        snapshot = self.memory_service.persist_turn(state, repo)
        state["db"].commit()
        return {"summary": snapshot.get("summary", state.get("summary", ""))}

    def handoff_ticket(self, state: AgentState) -> dict:
        """在需要人工介入时生成工单。"""
        repo = ShopRepository(state["db"])
        reason = state.get("handoff_reason") or "用户主动要求人工"
        summary = self.brain.summarize_handoff(
            {
                "user_id": state["user_id"],
                "session_id": state["session_id"],
                "reason": reason,
                "message": state["user_message"],
                "intent": state.get("intent"),
                "order_id": state.get("slots", {}).get("order_id"),
                "reply": state.get("final_reply"),
            }
        )
        ticket = repo.create_ticket(state["session_id"], state["user_id"], reason, summary)
        state["db"].commit()
        return {"handoff_ticket_id": ticket.ticket_no}

    @staticmethod
    def _route_after_intent(state: AgentState) -> str:
        """根据意图和槽位完整度决定下一步节点。"""
        if state.get("missing_fields"):
            return "collect_missing_info"
        if state.get("intent") in {"product_consultation", "promotion_policy", "general"}:
            return "retrieve_from_milvus"
        if state.get("intent") == "logistics_query":
            return "query_order_tool"
        if state.get("intent") == "return_refund":
            return "query_order_tool"
        return "response_generator"

    @staticmethod
    def _route_after_order_lookup(state: AgentState) -> str:
        """退货问题在查单后还要继续走规则判断，其它问题可以直接回复。"""
        if state.get("intent") == "return_refund":
            return "policy_checker"
        return "response_generator"

    @staticmethod
    def _route_after_persist(state: AgentState) -> str:
        """持久化结束后，根据是否需要人工来决定是否创建工单。"""
        return "handoff_ticket" if state.get("needs_handoff") else "end"

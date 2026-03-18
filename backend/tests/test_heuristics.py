"""启发式规则的基础回归测试。"""

from app.services.heuristics import extract_order_id, infer_intent


def test_extract_order_id():
    """应当从用户文本中提取标准订单号。"""
    assert extract_order_id("帮我查下 ORD-10001 的物流") == "ORD-10001"


def test_infer_intent_for_refund():
    """退款类问题应被正确识别为售后意图。"""
    intent, confidence = infer_intent("订单 ORD-10003 能退货吗")
    assert intent == "return_refund"
    assert confidence > 0.8

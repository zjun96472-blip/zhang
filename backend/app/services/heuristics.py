"""不依赖大模型的轻量级启发式规则。"""

import re


# 订单号格式在演示系统中固定为 `ORD-xxxxx`。
ORDER_ID_PATTERN = re.compile(r"ORD-\d{5}", re.IGNORECASE)


def extract_order_id(text: str) -> str | None:
    """从用户输入里提取订单号。"""
    match = ORDER_ID_PATTERN.search(text)
    if not match:
        return None
    return match.group(0).upper()


def infer_intent(message: str) -> tuple[str, float]:
    """在 mock 模式或兜底场景下，用关键词快速推断用户意图。"""
    text = message.lower()
    if any(keyword in text for keyword in ["赔", "投诉", "人工", "不满意", "差评", "补偿"]):
        return "complaint_handoff", 0.86
    if any(keyword in text for keyword in ["物流", "快递", "发货", "到哪", "订单在哪"]):
        return "logistics_query", 0.84
    if any(keyword in text for keyword in ["退款", "退货", "换货", "售后", "无理由"]):
        return "return_refund", 0.83
    if any(keyword in text for keyword in ["优惠", "券", "折扣", "红包", "满减"]):
        return "promotion_policy", 0.8
    if any(
        keyword in text
        for keyword in ["区别", "参数", "适合", "推荐", "耳机", "榨汁杯", "台灯", "数位板", "午睡枕", "保温杯"]
    ):
        return "product_consultation", 0.82
    return "general", 0.66


def extract_compensation_risk(message: str) -> bool:
    """识别投诉、赔偿等高风险词，供风控节点直接转人工。"""
    text = message.lower()
    return any(keyword in text for keyword in ["赔偿", "补偿", "投诉", "举报", "平台介入", "人工"])


def normalize_product_keyword(message: str, candidates: list[str]) -> str | None:
    """从候选商品名列表里找到用户提及的具体商品。"""
    lowered = message.lower()
    for candidate in candidates:
        if candidate.lower() in lowered:
            return candidate
    return None

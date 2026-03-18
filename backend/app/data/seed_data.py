"""本地演示用的模拟数据。

这些数据在应用启动时被写入 MySQL，并参与 Milvus 知识库构建。
"""

from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    """生成去掉时区信息的 UTC 时间，便于写入当前数据库字段。"""
    return datetime.now(UTC).replace(tzinfo=None)


# 演示账号用于本地登录和会话隔离展示。
USERS = [
    {
        "id": "demo-user",
        "email": "demo@shopmate.local",
        "display_name": "演示用户",
        "password": "demo123456",
    },
    {
        "id": "campus-user",
        "email": "campus@shopmate.local",
        "display_name": "校园用户",
        "password": "campus123456",
    },
]


# 商品主数据既用于订单关联，也会被转成知识库文档供检索。
PRODUCTS = [
    {
        "product_code": "P1001",
        "name": "AeroFit 智能运动耳机",
        "category": "audio",
        "price": "499",
        "highlights": "开放式佩戴、IPX5 防水、跑步稳固不掉、24 小时续航",
        "specs": "蓝牙 5.4，单次续航 8 小时，充电盒 16 小时，重量 7.2g",
        "audience": "通勤与健身用户",
    },
    {
        "product_code": "P1002",
        "name": "NorthLake 保温随行杯",
        "category": "drinkware",
        "price": "159",
        "highlights": "316L 不锈钢、12 小时保温、可单手开盖",
        "specs": "容量 480ml，重量 290g，支持车载杯架",
        "audience": "办公室与学生用户",
    },
    {
        "product_code": "P1003",
        "name": "CloudRest 记忆棉午睡枕",
        "category": "home",
        "price": "239",
        "highlights": "慢回弹记忆棉、便携收纳、可拆洗外套",
        "specs": "展开 32x28cm，收纳后直径 13cm",
        "audience": "办公室与差旅用户",
    },
    {
        "product_code": "P1004",
        "name": "Spark Mini 便携榨汁杯",
        "category": "kitchen",
        "price": "199",
        "highlights": "一键榨汁、自清洁、Type-C 充电",
        "specs": "容量 420ml，电池 1500mAh，食品级 Tritan 杯体",
        "audience": "宿舍与健身用户",
    },
    {
        "product_code": "P1005",
        "name": "SlatePad 数位绘画板",
        "category": "digital",
        "price": "699",
        "highlights": "8192 级压感、轻薄机身、兼容 Windows/macOS",
        "specs": "工作区域 10 英寸，Type-C 接口，附赠无源笔",
        "audience": "设计初学者与插画爱好者",
    },
    {
        "product_code": "P1006",
        "name": "GlowDesk 氛围台灯",
        "category": "lighting",
        "price": "269",
        "highlights": "三档色温、无频闪、支持定时关闭",
        "specs": "最高亮度 700lm，USB-C 供电",
        "audience": "书桌办公和夜间阅读用户",
    },
]


# FAQ 文档偏通用问答，主要覆盖物流、发票、优惠等高频问题。
FAQ_DOCS = [
    {
        "id": "faq-001",
        "doc_type": "faq",
        "source": "FAQ/物流",
        "category": "shipping",
        "content": "现货商品通常在 24 小时内发出，大促期间最晚 72 小时内发出。",
    },
    {
        "id": "faq-002",
        "doc_type": "faq",
        "source": "FAQ/发票",
        "category": "invoice",
        "content": "订单签收后可在订单详情页申请电子发票，企业抬头与个人抬头都支持。",
    },
    {
        "id": "faq-003",
        "doc_type": "faq",
        "source": "FAQ/耳机",
        "category": "product",
        "content": "AeroFit 智能运动耳机支持通勤、跑步与轻度抗汗场景，不建议在游泳中使用。",
    },
    {
        "id": "faq-004",
        "doc_type": "faq",
        "source": "FAQ/榨汁杯",
        "category": "product",
        "content": "Spark Mini 便携榨汁杯支持制作奶昔、果汁和代餐饮品，硬质冰块需先打碎再使用。",
    },
    {
        "id": "faq-005",
        "doc_type": "faq",
        "source": "FAQ/售后",
        "category": "after_sales",
        "content": "如商品存在质量问题，请在签收后 48 小时内联系客服并上传照片，我们会优先协助处理。",
    },
    {
        "id": "faq-006",
        "doc_type": "faq",
        "source": "FAQ/优惠",
        "category": "promotion",
        "content": "店铺优惠券和平台红包通常可以叠加使用，具体以结算页展示为准。",
    },
]


# 售后政策文档偏规则型内容，主要用于售后判断和风控兜底。
POLICY_DOCS = [
    {
        "id": "policy-001",
        "doc_type": "policy",
        "source": "售后政策/7天无理由",
        "category": "return",
        "content": "支持签收后 7 天内无理由退货，商品需保持完好，不影响二次销售。",
    },
    {
        "id": "policy-002",
        "doc_type": "policy",
        "source": "售后政策/退款时效",
        "category": "refund",
        "content": "退款申请审核通过后，原路退款通常在 1 到 5 个工作日内到账。",
    },
    {
        "id": "policy-003",
        "doc_type": "policy",
        "source": "售后政策/物流拒收",
        "category": "shipping",
        "content": "若包裹未签收，可在物流派送前联系客服协助拦截或拒收。",
    },
    {
        "id": "policy-004",
        "doc_type": "policy",
        "source": "售后政策/赔付",
        "category": "complaint",
        "content": "涉及赔付、补偿、严重投诉等场景需由人工客服审核，机器人不可直接承诺金额。",
    },
]


# 订单数据覆盖已签收、运输中、退款处理中等状态，方便演示不同客服流程。
ORDERS = [
    {
        "order_id": "ORD-10001",
        "user_id": "demo-user",
        "product_code": "P1001",
        "status": "delivered",
        "logistics_status": "已签收",
        "tracking_no": "SF100000001",
        "refund_status": "none",
        "ordered_at": _utcnow() - timedelta(days=4),
        "delivered_at": _utcnow() - timedelta(days=2),
        "metadata_json": {"address_city": "Shanghai"},
    },
    {
        "order_id": "ORD-10002",
        "user_id": "demo-user",
        "product_code": "P1004",
        "status": "shipped",
        "logistics_status": "运输中",
        "tracking_no": "YT100000002",
        "refund_status": "none",
        "ordered_at": _utcnow() - timedelta(days=2),
        "delivered_at": None,
        "metadata_json": {"address_city": "Suzhou"},
    },
    {
        "order_id": "ORD-10003",
        "user_id": "demo-user",
        "product_code": "P1005",
        "status": "delivered",
        "logistics_status": "已签收",
        "tracking_no": "JD100000003",
        "refund_status": "none",
        "ordered_at": _utcnow() - timedelta(days=18),
        "delivered_at": _utcnow() - timedelta(days=12),
        "metadata_json": {"address_city": "Hangzhou"},
    },
    {
        "order_id": "ORD-10004",
        "user_id": "demo-user",
        "product_code": "P1002",
        "status": "refund_processing",
        "logistics_status": "已签收",
        "tracking_no": "ZT100000004",
        "refund_status": "processing",
        "ordered_at": _utcnow() - timedelta(days=7),
        "delivered_at": _utcnow() - timedelta(days=5),
        "metadata_json": {"address_city": "Nanjing"},
    },
    {
        "order_id": "ORD-10005",
        "user_id": "campus-user",
        "product_code": "P1006",
        "status": "delivered",
        "logistics_status": "已签收",
        "tracking_no": "SF100000005",
        "refund_status": "none",
        "ordered_at": _utcnow() - timedelta(days=3),
        "delivered_at": _utcnow() - timedelta(days=1),
        "metadata_json": {"address_city": "Beijing"},
    },
]

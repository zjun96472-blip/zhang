"""售后规则判断模块。"""

from datetime import UTC, datetime, timedelta


def evaluate_return_policy(order: dict | None, now: datetime | None = None) -> dict:
    """根据订单状态判断是否满足退货条件。

    这里故意保持规则简单，方便在简历项目里清晰讲解：
    1. 没有订单信息就无法判断
    2. 已进入退款流程的订单不重复发起
    3. 未签收订单优先走物流拦截/拒收
    4. 签收后 7 天内支持无理由退货
    """

    if not order:
        return {
            "eligible": False,
            "reason": "未找到对应订单，暂时无法判断退货资格。",
            "next_step": "请先提供正确的订单号。",
            "policy_source": "售后政策/7天无理由",
        }

    if order.get("refund_status") in {"processing", "refunded"}:
        return {
            "eligible": False,
            "reason": "该订单已进入退款流程，建议等待系统审核结果。",
            "next_step": "如超过 48 小时仍无进展，可转人工继续跟进。",
            "policy_source": "售后政策/退款时效",
        }

    delivered_at = order.get("delivered_at")
    if delivered_at is None:
        return {
            "eligible": False,
            "reason": "商品尚未签收，当前更适合处理物流或拒收，不建议直接走退货。",
            "next_step": "若希望取消订单，可联系客服协助拦截或拒收。",
            "policy_source": "售后政策/物流拒收",
        }

    now = now or datetime.now(UTC).replace(tzinfo=None)
    deadline = delivered_at + timedelta(days=7)
    if now <= deadline and order.get("status") in {"delivered", "completed"}:
        return {
            "eligible": True,
            "reason": "订单仍在签收后 7 天内，满足无理由退货的时间条件。",
            "next_step": "保持商品与配件完整，并在订单页提交退货申请。",
            "policy_source": "售后政策/7天无理由",
        }

    return {
        "eligible": False,
        "reason": "订单已超过签收后 7 天，当前不满足无理由退货时限。",
        "next_step": "如商品存在质量问题，可补充照片后转人工协助。",
        "policy_source": "售后政策/7天无理由",
    }

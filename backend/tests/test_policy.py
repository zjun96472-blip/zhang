"""售后规则的单元测试。"""

from datetime import UTC, datetime, timedelta

from app.services.policy import evaluate_return_policy


def test_return_policy_accepts_recent_delivery():
    """签收后 7 天内的订单应满足无理由退货时效。"""
    result = evaluate_return_policy(
        {
            "status": "delivered",
            "refund_status": "none",
            "delivered_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3),
        }
    )

    assert result["eligible"] is True
    assert "7 天内" in result["reason"]


def test_return_policy_rejects_expired_order():
    """超出时限的订单应被拒绝。"""
    result = evaluate_return_policy(
        {
            "status": "delivered",
            "refund_status": "none",
            "delivered_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10),
        }
    )

    assert result["eligible"] is False
    assert "超过" in result["reason"]

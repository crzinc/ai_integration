"""Tests for router module."""

import pytest
from router import get_routing_target, format_routing_message
from models import Category, Priority


class TestRoutingTarget:
    def test_sales_routing_no_chat_id(self):
        result = get_routing_target(Category.SALES.value, Priority.MEDIUM.value)
        assert result["department"] == Category.SALES.value
        # With default config (chat_id=0), should_notify is False
        assert result["should_notify"] is False

    def test_critical_escalation(self):
        result = get_routing_target(Category.SUPPORT.value, Priority.CRITICAL.value)
        assert result["escalate"] is True

    def test_unknown_no_routing(self):
        result = get_routing_target(Category.UNKNOWN.value, Priority.LOW.value)
        assert result["should_notify"] is False

    def test_spam_no_routing(self):
        result = get_routing_target(Category.SPAM.value, Priority.LOW.value)
        assert result["should_notify"] is False


class TestFormatMessage:
    def test_format_includes_ticket_id(self):
        text = format_routing_message(
            "Test message",
            {"category": "sales", "priority": "medium", "confidence": 0.8, "sentiment": "neutral"},
            {"name": "John", "username": "john_doe"},
            ticket_id=42,
        )
        assert "#42" in text
        assert "john_doe" in text

"""Tests for autoresponder module."""

import pytest
from autoresponder import should_auto_respond, get_auto_response
from models import Category, Priority


class TestAutoRespond:
    def test_should_respond_high_confidence(self):
        classification = {
            "category": Category.SALES.value,
            "priority": Priority.MEDIUM.value,
            "confidence": 0.9,
        }
        assert should_auto_respond(classification) is True

    def test_should_not_respond_low_confidence(self):
        classification = {
            "category": Category.SALES.value,
            "priority": Priority.MEDIUM.value,
            "confidence": 0.3,
        }
        assert should_auto_respond(classification) is False

    def test_should_not_respond_spam(self):
        classification = {
            "category": Category.SPAM.value,
            "priority": Priority.LOW.value,
            "confidence": 0.9,
        }
        assert should_auto_respond(classification) is False

    def test_should_not_respond_critical(self):
        classification = {
            "category": Category.SUPPORT.value,
            "priority": Priority.CRITICAL.value,
            "confidence": 0.95,
        }
        assert should_auto_respond(classification) is False

    def test_get_response_sales(self):
        response = get_auto_response({"category": Category.SALES.value})
        assert response is not None
        assert "отделу продаж" in response.lower() or "менеджер" in response.lower()

    def test_get_response_unknown(self):
        response = get_auto_response({"category": Category.UNKNOWN.value})
        assert response is None

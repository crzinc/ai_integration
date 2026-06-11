"""Tests for classifier module."""

import pytest
from classifier import classify_by_keywords, KEYWORD_RULES
from models import Category


class TestKeywordClassifier:
    def test_sales_detection(self):
        result = classify_by_keywords("Хочу купить ваш продукт, какова цена?")
        assert result is not None
        assert result["category"] == Category.SALES.value
        assert result["confidence"] > 0

    def test_support_detection(self):
        result = classify_by_keywords("У меня не работает интеграция, help!")
        assert result is not None
        assert result["category"] == Category.SUPPORT.value

    def test_technical_detection(self):
        result = classify_by_keywords("Как настроить API webhook endpoint?")
        assert result is not None
        assert result["category"] == Category.TECHNICAL.value

    def test_billing_detection(self):
        result = classify_by_keywords("Хочу сделать возврат, не пришёл счёт на оплату")
        assert result is not None
        assert result["category"] == Category.BILLING.value

    def test_management_detection(self):
        result = classify_by_keywords("Я хочу подать жалобу руководителю")
        assert result is not None
        assert result["category"] == Category.MANAGEMENT.value
        assert result["priority"] == "high"

    def test_no_match(self):
        result = classify_by_keywords("Привет, как дела?")
        assert result is None

    def test_empty_message(self):
        result = classify_by_keywords("")
        assert result is None

    def test_confidence_range(self):
        result = classify_by_keywords("купить тариф цена")
        assert result is not None
        assert 0 <= result["confidence"] <= 1


class TestKeywordRules:
    def test_all_categories_have_keywords(self):
        for category in Category:
            if category in (Category.SPAM, Category.UNKNOWN):
                continue
            assert category.value in KEYWORD_RULES

    def test_keywords_are_non_empty(self):
        for category, rules in KEYWORD_RULES.items():
            assert len(rules["keywords"]) > 0, f"No keywords for {category}"

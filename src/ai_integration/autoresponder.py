from __future__ import annotations

import structlog

from .config import settings
from .models import Category, Priority

logger = structlog.get_logger()

# Pre-defined responses for common scenarios
TEMPLATE_RESPONSES: dict[str, dict] = {
    Category.SALES.value: {
        "default": (
            "\U0001f44b Спасибо за интерес к нашему продукту!\n\n"
            "Ваше обращение зарегистрировано и передано отделу продаж. "
            "Наш менеджер свяжется с вами в ближайшее время.\n\n"
            "\U0001f4cb Что يمكن подготовить заранее:\n"
            "- Презентация продукта под ваши задачи\n"
            "- Сравнение тарифных планов\n"
            "- Пробный доступ для оценки\n\n"
            "Ожидайте ответа в течение рабочего дня."
        ),
        "demo_request": (
            "\U0001f3ac Отлично! Вы хотите посмотреть демо?\n\n"
            "Мы можем провести:\n"
            "- \U0001f4bb Онлайн-презентацию (30 мин)\n"
            "- \U0001f9ea Тестовый доступ на 14 дней\n"
            "- \U0001f4cb Индивидуальный разбор под ваши задачи\n\n"
            "Наш менеджер скоро свяжется с вами!"
        ),
    },
    Category.SUPPORT.value: {
        "default": (
            "\U0001f6e0\ufe0f Мы получили ваш запрос в техническую поддержку.\n\n"
            "Наш специалист изучит проблему и ответит вам. "
            "Для ускорения решения, пожалуйста, предоставьте:\n\n"
            "\u2022 Шаги для воспроизведения проблемы\n"
            "\u2022 Скриншоты или видео (если возможно)\n"
            "\u2022 Информацию о браузере/устройстве\n\n"
            "Среднее время ответа: 2-4 часа в рабочее время."
        ),
    },
    Category.TECHNICAL.value: {
        "default": (
            "\U0001f527 Технический запрос принят.\n\n"
            "Наш инженер свяжется с вами для обсуждения деталей интеграции.\n\n"
            "\U0001f4da Полезные ресурсы:\n"
            "- Документация: docs.example.com\n"
            "- API Reference: api.example.com\n"
            "- Sandbox: sandbox.example.com\n\n"
            "Ожидайте ответа в течение рабочего дня."
        ),
    },
    Category.BILLING.value: {
        "default": (
            "\U0001f4b3 Ваш вопрос по оплате принят.\n\n"
            "Мы обработаем ваш запрос в ближайшее время.\n"
            "Для ускорения укажите:\n"
            "- Номер счета или детали подписки\n"
            "- Желаемое действие\n\n"
            "Среднее время ответа: 1-2 рабочих дня."
        ),
    },
}


def should_auto_respond(classification: dict) -> bool:
    """Determine if we should send an auto-response."""
    if not settings.auto_response_enabled:
        return False

    confidence = classification.get("confidence", 0)
    category = classification.get("category", "")
    priority = classification.get("priority", "")

    # Don't auto-respond to spam or unknown
    if category in (Category.SPAM.value, Category.UNKNOWN.value):
        return False

    # Don't auto-respond to critical - need human immediately
    if priority == Priority.CRITICAL.value:
        return False

    # Check confidence threshold
    if confidence < settings.confidence_threshold:
        return False

    # Check if we have a template
    if category not in TEMPLATE_RESPONSES:
        return False

    return True


def get_auto_response(classification: dict) -> str | None:
    """Get an appropriate auto-response message."""
    category = classification.get("category", "")
    subcategory = classification.get("subcategory", "")

    templates = TEMPLATE_RESPONSES.get(category, {})
    if not templates:
        return None

    # Try subcategory-specific response first
    if subcategory and subcategory in templates:
        return templates[subcategory]

    return templates.get("default")

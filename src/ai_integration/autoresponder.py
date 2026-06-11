"""Auto-responder — generates unique replies using LLM with interesting facts."""

from __future__ import annotations

import random

import structlog
from openai import AsyncOpenAI

from .config import settings
from .models import Category, Priority

logger = structlog.get_logger()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
        )
    return _client


INTERESTING_FACTS = [
    "Кстати, первый компьютер весил 27 тонн и занимал целую комнату!",
    "Интересный факт: 90% всех данных в мире было создано за последние 2 года.",
    "Знаете ли вы? Среднее время концентрации человека сейчас — 8 секунд, меньше, чем у золотой рыбки.",
    "Факт: первый спам-емейл был отправлен в 1978 году и reaching 400 человек.",
    "Интересно: слово 'робот' придумал чешский писатель в 1920 году, означает 'работа'.",
    "Факт: AI может написать стихотворение быстрее, чем вы прочитаете это предложение.",
    "Знаете ли вы? Более 80% всех входящих писем — спам.",
    "Интересный факт: человеческий мозг обрабатывает изображения за 13 миллисекунд.",
    "Факт: первый website в мире до сих пор работает — info.cern.ch.",
    "Интересно: 93% всех онлайн-сессий начинаются с поисковой системы.",
    "Факт: средний пользователь проверяет телефон 96 раз в день.",
    "Знаете ли вы? Нейросети могут учиться на данных быстрее, чем студенты перед экзаменом!",
    "Интересный факт: 5G работает в 100 раз быстрее, чем 4G.",
    "Факт: к 2025 году в мире будет более 75 миллиардов IoT-устройств.",
    "Интересно: первый электронный компьютер весил 27 тонн, а сейчас у вас в кармане устройство в тысячи раз мощнее.",
]


CATEGORY_CONTEXT = {
    Category.SALES.value: (
        "отдел продаж B2B/SaaS компании. "
        "Клиент заинтересован в продукте, тарифах или демо. "
        "Будь дружелюбным, предложи помощь, подчеркни ценность продукта."
    ),
    Category.SUPPORT.value: (
        "техническая поддержка B2B/SaaS компании. "
        "У клиента проблема или вопрос по продукту. "
        "Будь empathetic, покажи что проблема будет решена, предложи шаги."
    ),
    Category.TECHNICAL.value: (
        "технический отдел B2B/SaaS компании. "
        "Клиент спрашивает об API, интеграциях или настройках. "
        "Будь компетентным, предложи документацию и ресурсы."
    ),
    Category.BILLING.value: (
        "отдел биллинга B2B/SaaS компании. "
        "Клиент спрашивает об оплате, счетах или подписке. "
        "Будь вежливым, уточни детали для ускорения."
    ),
    Category.MANAGEMENT.value: (
        "отдел руководства B2B/SaaS компании. "
        "Клиент хочет поговорить с руководством или жалуется. "
        "Будь особенно вежливым, заверь что обращение будет рассмотрено."
    ),
}

CATEGORY_LABELS = {
    Category.SALES.value: "отдел продаж",
    Category.SUPPORT.value: "техподдержка",
    Category.TECHNICAL.value: "технический отдел",
    Category.BILLING.value: "отдел биллинга",
    Category.MANAGEMENT.value: "руководство",
}

AUTO_REPLY_PROMPT = """Ты — дружелюбный AI-ассистент B2B/SaaS компании.

Напиши короткий автоответ клиенту на его обращение.

КОНТЕКСТ: {context}
СООБЩЕНИЕ КЛИЕНТА: {message}

ПРАВИЛА:
- Будь кратким (3-5 предложений максимум)
- Подтверди получение обращения
- Скажи что специалист свяжется в ближайшее время
- Добавь один интересный факт или совет в конце (смайлик)
- Не используй markdown
- Не пиши длинные списки
- Пиши на русском языке
- НЕ начинай с "Здравствуйте" — начни сразу с подтверждения

ОТВЕТ (только текст, без кавычек):"""


async def generate_auto_response(
    message_text: str,
    category: str,
) -> str | None:
    """Generate a unique auto-response using LLM."""
    context = CATEGORY_CONTEXT.get(category)
    if not context:
        return None

    prompt = AUTO_REPLY_PROMPT.format(
        context=context,
        message=message_text[:500],
    )

    try:
        response = await _get_client().chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=200,
        )

        text = response.choices[0].message.content
        if text:
            text = text.strip().strip('"').strip("'")
            if len(text) > 20:
                return text

    except Exception as e:
        logger.error("llm_auto_response_failed", error=str(e))

    return None


def get_fallback_response(category: str) -> str:
    """Static fallback responses if LLM fails."""
    fact = random.choice(INTERESTING_FACTS)
    label = CATEGORY_LABELS.get(category, "специалист")

    templates = {
        Category.SALES.value: (
            "Ваше обращение получено! "
            "Наш менеджер по продажам свяжется с вами в ближайшее время, "
            "чтобы обсудить ваши задачи и подобрать лучшее решение.\n\n"
            f"💡 {fact}"
        ),
        Category.SUPPORT.value: (
            "Мы получили ваш запрос в техподдержку! "
            "Наш специалист уже приступает к его изучению и ответит вам скоро.\n\n"
            f"💡 {fact}"
        ),
        Category.TECHNICAL.value: (
            "Технический запрос принят! "
            "Наш инженер свяжется с вами для обсуждения деталей.\n\n"
            f"💡 {fact}"
        ),
        Category.BILLING.value: (
            "Ваш вопрос по оплате принят! "
            "Мы обработаем его в ближайшее время.\n\n"
            f"💡 {fact}"
        ),
        Category.MANAGEMENT.value: (
            "Ваше обращение зарегистрировано и будет передано руководству. "
            "Мы отнесёмся к вашему вопросу с особым вниманием.\n\n"
            f"💡 {fact}"
        ),
    }

    return templates.get(category, f"Ваш запрос принят в обработку. {label} ответит вам скоро.\n\n💡 {fact}")


def should_auto_respond(classification: dict) -> bool:
    """Determine if we should send an auto-response."""
    if not settings.auto_response_enabled:
        return False

    confidence = classification.get("confidence", 0)
    category = classification.get("category", "")
    priority = classification.get("priority", "")

    if category in (Category.SPAM.value, Category.UNKNOWN.value):
        return False
    if priority == Priority.CRITICAL.value:
        return False
    if confidence < settings.confidence_threshold:
        return False

    return category in CATEGORY_CONTEXT


async def get_auto_response(
    message_text: str,
    category: str,
) -> str | None:
    """Generate unique auto-response via LLM, fallback to static."""
    # Try LLM first
    llm_response = await generate_auto_response(message_text, category)
    if llm_response:
        return llm_response

    # Fallback to static
    return get_fallback_response(category)

from __future__ import annotations

import json

import structlog
from openai import AsyncOpenAI

from .config import settings
from .models import Category, Priority

logger = structlog.get_logger()

_client: AsyncOpenAI | None = None

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
        )
    return _client

CLASSIFICATION_PROMPT = """Ты — система классификации обращений клиентов B2B/SaaS компании.

Классифицируй сообщение клиента по категориям, приоритету и настроению.

КАТЕГОРИИ:
- sales: вопросы о покупке, тарифах, demos, коммерческие предложения
- support: техническая поддержка, баги, вопросы по функционалу
- technical: интеграции, API, настройки, DevOps вопросы
- billing: оплаты, счета, возвраты, подписки
- management: жалобы, эскалация, вопросы руководству
- spam: спам, реклама, не относится к продукту

ПРИОРИТЕТЫ:
- low: общие вопросы, нет срочности
- medium: стандартные обращения
- high: важные вопросы, влияющие на бизнес
- critical: критические проблемы, простоя, потеря данных

ОТВЕТ В ФОРМАТЕ JSON:
{
  "category": "одна из категорий",
  "subcategory": "подкатегория (если возможно)",
  "priority": "приоритет",
  "sentiment": "positive/neutral/negative/angry",
  "confidence": 0.0-1.0,
  "reasoning": "краткое объяснение решения",
  "auto_response": "текст автоответа (null если нужен живой человек)",
  "keywords": ["ключевые слова для поиска"]
}

Сообщение клиента:
---
{message}
---

Ответ (только JSON):"""


async def classify_message(
    message_text: str, user_context: str = ""
) -> dict:
    """Classify a customer message using LLM."""
    prompt = CLASSIFICATION_PROMPT.replace("{message}", message_text)

    if user_context:
        prompt = f"Контекст пользователя: {user_context}\n\n" + prompt

    raw_content = "{}"
    try:
        response = await _get_client().chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        raw_content = response.choices[0].message.content or "{}"

        logger.debug("raw_llm_response", content=raw_content[:500])

        # Try to extract JSON from response (some models wrap it in markdown)
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0]
        elif "```" in raw_content:
            raw_content = raw_content.split("```")[1].split("```")[0]

        raw_content = raw_content.strip()

        # Handle cases where model wraps JSON in quotes
        if raw_content.startswith('"') and raw_content.endswith('"'):
            raw_content = raw_content[1:-1]

        logger.debug("parsed_llm_content", content=raw_content[:500])

        result = json.loads(raw_content)

        if not isinstance(result, dict):
            raise ValueError(f"Expected dict, got {type(result).__name__}")

        # Validate and normalize
        category = result.get("category", Category.UNKNOWN.value)
        if category not in [c.value for c in Category]:
            category = Category.UNKNOWN.value

        priority = result.get("priority", Priority.MEDIUM.value)
        if priority not in [p.value for p in Priority]:
            priority = Priority.MEDIUM.value

        confidence = float(result.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        logger.info(
            "message_classified",
            category=category,
            priority=priority,
            confidence=confidence,
        )

        return {
            "category": category,
            "subcategory": result.get("subcategory"),
            "priority": priority,
            "sentiment": result.get("sentiment", "neutral"),
            "confidence": confidence,
            "reasoning": result.get("reasoning", ""),
            "auto_response": result.get("auto_response"),
            "keywords": result.get("keywords", []),
        }

    except Exception as e:
        logger.error("classification_error", error=str(e), raw_content=raw_content[:500])
        return {
            "category": Category.UNKNOWN.value,
            "subcategory": None,
            "priority": Priority.MEDIUM.value,
            "sentiment": "neutral",
            "confidence": 0.0,
            "reasoning": f"Classification failed: {e}",
            "auto_response": None,
            "keywords": [],
        }


# Keyword-based fallback classifier (no LLM needed)
KEYWORD_RULES: dict[str, dict] = {
    Category.SALES.value: {
        "keywords": [
            "купить", "тариф", "цена", "стоимость", "демо", "демонстрация",
            "пробный", "trial", "лицензия", "subscription", "подписка",
            "предложение", "contract", "договор", "commerc",
        ],
        "priority_boost": False,
    },
    Category.SUPPORT.value: {
        "keywords": [
            "не работает", "баг", "ошибка", "проблема", "help", "помощь",
            "поддержка", "support", "сломал", "не могу", "не открывает",
            "вылетает", "crash", "глюк",
        ],
        "priority_boost": True,
    },
    Category.TECHNICAL.value: {
        "keywords": [
            "api", "интеграция", "webhook", "sandbox", "token", "endpoint",
            "SDK", "документац", "настройк", "конфигурац", "server",
            "сервер", "database", "база данных",
        ],
        "priority_boost": False,
    },
    Category.BILLING.value: {
        "keywords": [
            "оплат", "счёт", "invoice", "возврат", "refund", "платёж",
            "payment", "карта", "bank", "банк", "счёт", "balance",
        ],
        "priority_boost": False,
    },
    Category.MANAGEMENT.value: {
        "keywords": [
            "руководител", "менеджер", "жалоб", "complaint", "обращение",
            "директор", "legal", "юридическ", "претензи",
        ],
        "priority_boost": True,
    },
}


def classify_by_keywords(message_text: str) -> dict | None:
    """Simple keyword-based classification as fallback."""
    text_lower = message_text.lower()
    scores: dict[str, int] = {}

    for category, rules in KEYWORD_RULES.items():
        score = sum(1 for kw in rules["keywords"] if kw.lower() in text_lower)
        if score > 0:
            scores[category] = score

    if not scores:
        return None

    best_category = max(scores, key=scores.get)  # type: ignore[arg-type]
    total_hits = sum(scores.values())
    confidence = scores[best_category] / max(total_hits, 1)

    return {
        "category": best_category,
        "subcategory": None,
        "priority": Priority.HIGH.value if KEYWORD_RULES[best_category]["priority_boost"] else Priority.MEDIUM.value,
        "sentiment": "negative" if best_category == Category.MANAGEMENT.value else "neutral",
        "confidence": min(confidence + 0.1, 0.95),
        "reasoning": f"Keyword match: {scores[best_category]} hits for {best_category}",
        "auto_response": None,
        "keywords": [],
    }

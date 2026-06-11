from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    telegram_bot_token: str = Field(default="", description="Telegram Bot API token")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_model: str = Field(
        default="qwen/qwen-2-7b-instruct:free",
        description="Model for classification (free tier)",
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./classifier.db",
        description="Async database URL",
    )

    log_level: str = Field(default="INFO")

    routing_sales_chat_id: int = Field(default=0, description="Chat ID for Sales team")
    routing_support_chat_id: int = Field(default=0, description="Chat ID for Support team")
    routing_tech_chat_id: int = Field(default=0, description="Chat ID for Tech team")
    routing_billing_chat_id: int = Field(default=0, description="Chat ID for Billing team")
    routing_management_chat_id: int = Field(default=0, description="Chat ID for Management")

    auto_response_enabled: bool = Field(default=True)
    confidence_threshold: float = Field(
        default=0.7, description="Min confidence to auto-respond"
    )

    admin_chat_id: int = Field(default=0, description="Chat ID for admin notifications")

    dashboard_password: str = Field(default="admin123", description="Password for web dashboard")


settings = Settings()

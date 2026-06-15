from app.ai_models import AIProvider
from app.services.ai.providers.deepseek import DeepSeekAdapter
from app.services.ai.providers.volcengine import VolcengineAdapter


def create_adapter(provider: AIProvider, credentials: dict[str, str], base_url: str | None = None):
    if provider == AIProvider.deepseek:
        return DeepSeekAdapter(credentials, base_url)
    return VolcengineAdapter(credentials, base_url)

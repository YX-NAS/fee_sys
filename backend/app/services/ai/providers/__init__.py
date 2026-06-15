from app.ai_models import AIProvider
from app.services.ai.providers.alibaba import AlibabaAdapter
from app.services.ai.providers.deepseek import DeepSeekAdapter
from app.services.ai.providers.huawei import HuaweiAdapter
from app.services.ai.providers.kimi import KimiAdapter
from app.services.ai.providers.siliconflow import SiliconFlowAdapter
from app.services.ai.providers.volcengine import VolcengineAdapter
from app.services.ai.providers.zhipu import ZhipuAdapter


def create_adapter(provider: AIProvider, credentials: dict[str, str], base_url: str | None = None):
    if provider == AIProvider.deepseek:
        return DeepSeekAdapter(credentials, base_url)
    if provider == AIProvider.volcengine:
        return VolcengineAdapter(credentials, base_url)
    if provider == AIProvider.kimi:
        return KimiAdapter(credentials, base_url)
    if provider == AIProvider.alibaba:
        return AlibabaAdapter(credentials, base_url)
    if provider == AIProvider.huawei:
        return HuaweiAdapter(credentials, base_url)
    if provider == AIProvider.zhipu:
        return ZhipuAdapter(credentials, base_url)
    if provider == AIProvider.siliconflow:
        return SiliconFlowAdapter(credentials, base_url)
    raise ValueError(f"不支持的厂商: {provider}")

"""统一的大模型接入层。

支持 OpenAI-compatible、OpenAI、Azure OpenAI、Anthropic Claude、
Google Gemini 与 Ollama。业务 Agent 只依赖本模块，不感知具体厂商 SDK。
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import get_settings


_PROVIDER_ALIASES = {
    "openai-compatible": "openai_compatible",
    "compatible": "openai_compatible",
    "dashscope": "openai_compatible",
    "qwen": "openai_compatible",
    "deepseek": "openai_compatible",
    "moonshot": "openai_compatible",
    "siliconflow": "openai_compatible",
    "openrouter": "openai_compatible",
    "zhipu": "openai_compatible",
    "azure": "azure_openai",
    "azure-openai": "azure_openai",
    "claude": "anthropic",
    "google": "gemini",
}
_SUPPORTED_PROVIDERS = {
    "openai_compatible",
    "openai",
    "azure_openai",
    "anthropic",
    "gemini",
    "ollama",
}


def get_provider_name() -> str:
    """返回规范化后的 provider 名称，并对错误配置给出明确提示。"""
    raw = get_settings().llm_provider.strip().lower()
    provider = _PROVIDER_ALIASES.get(raw, raw)
    if provider not in _SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(_SUPPORTED_PROVIDERS))
        raise ValueError(f"不支持的 LLM_PROVIDER={raw!r}，可选值：{supported}")
    return provider


def _require(value: str, env_name: str, provider: str) -> str:
    if not value.strip():
        raise ValueError(f"使用 {provider} 时必须配置 {env_name}")
    return value.strip()


def _extra_body() -> dict[str, Any] | None:
    """解析厂商扩展参数，同时兼容部分推理模型的非流式调用限制。"""
    settings = get_settings()
    extra: dict[str, Any] = {}
    if settings.llm_extra_body.strip():
        try:
            parsed = json.loads(settings.llm_extra_body)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM_EXTRA_BODY 必须是合法的 JSON 对象") from exc
        if not isinstance(parsed, dict):
            raise ValueError("LLM_EXTRA_BODY 必须是 JSON 对象")
        extra.update(parsed)

    base_url = settings.llm_api_base.lower()
    model_name = settings.llm_model_name.lower()
    if "dashscope" in base_url and model_name.startswith(("qwen3", "glm-5")):
        extra.setdefault("enable_thinking", False)
    return extra or None


def _build_openai_chat(temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    provider = get_provider_name()
    api_key = _require(settings.llm_api_key, "LLM_API_KEY", provider)
    kwargs: dict[str, Any] = {
        "model": _require(settings.llm_model_name, "LLM_MODEL_NAME", provider),
        "api_key": api_key,
        "temperature": temperature,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }
    if provider == "openai_compatible":
        kwargs["base_url"] = _require(settings.llm_api_base, "LLM_API_BASE", provider)
    extra_body = _extra_body()
    if extra_body:
        kwargs["extra_body"] = extra_body
    return ChatOpenAI(**kwargs)


def _build_azure_chat(temperature: float) -> BaseChatModel:
    from langchain_openai import AzureChatOpenAI

    settings = get_settings()
    provider = get_provider_name()
    return AzureChatOpenAI(
        azure_endpoint=_require(settings.llm_api_base, "LLM_API_BASE", provider),
        azure_deployment=_require(settings.llm_model_name, "LLM_MODEL_NAME", provider),
        api_key=_require(settings.llm_api_key, "LLM_API_KEY", provider),
        api_version=settings.azure_openai_api_version,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def _build_anthropic_chat(temperature: float) -> BaseChatModel:
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError("Anthropic 适配器未安装，请执行 pip install langchain-anthropic") from exc

    settings = get_settings()
    provider = get_provider_name()
    kwargs: dict[str, Any] = {
        "model": _require(settings.llm_model_name, "LLM_MODEL_NAME", provider),
        "api_key": _require(settings.llm_api_key, "LLM_API_KEY", provider),
        "temperature": temperature,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }
    if settings.llm_api_base:
        kwargs["base_url"] = settings.llm_api_base
    return ChatAnthropic(**kwargs)


def _build_gemini_chat(temperature: float) -> BaseChatModel:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError(
            "Gemini 适配器未安装，请执行 pip install langchain-google-genai"
        ) from exc

    settings = get_settings()
    provider = get_provider_name()
    return ChatGoogleGenerativeAI(
        model=_require(settings.llm_model_name, "LLM_MODEL_NAME", provider),
        api_key=_require(settings.llm_api_key, "LLM_API_KEY", provider),
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def _build_ollama_chat(temperature: float) -> BaseChatModel:
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError("Ollama 适配器未安装，请执行 pip install langchain-ollama") from exc

    settings = get_settings()
    provider = get_provider_name()
    return ChatOllama(
        model=_require(settings.llm_model_name, "LLM_MODEL_NAME", provider),
        base_url=settings.llm_api_base or "http://127.0.0.1:11434",
        temperature=temperature,
    )


@lru_cache()
def get_llm(temperature: float = 0.3) -> BaseChatModel:
    """按 LLM_PROVIDER 创建并缓存统一的 LangChain ChatModel。"""
    provider = get_provider_name()
    if provider in {"openai", "openai_compatible"}:
        return _build_openai_chat(temperature)
    if provider == "azure_openai":
        return _build_azure_chat(temperature)
    if provider == "anthropic":
        return _build_anthropic_chat(temperature)
    if provider == "gemini":
        return _build_gemini_chat(temperature)
    return _build_ollama_chat(temperature)


def get_creative_llm() -> BaseChatModel:
    """获取用于创意和方案生成的模型。"""
    return get_llm(temperature=0.7)


def get_structured_llm(schema, *, temperature: float = 0.3, method: str | None = None):
    """绑定 Pydantic Schema，并兼容不同 provider 的参数差异。"""
    llm = get_llm(temperature)
    provider = get_provider_name()
    if provider in {"openai", "openai_compatible", "azure_openai"}:
        structured_method = method or get_settings().structured_output_method
        return llm.with_structured_output(schema, method=structured_method)
    return llm.with_structured_output(schema)


def get_llm_with_tools(tools: list, *, temperature: float = 0.3):
    """为支持工具调用的模型绑定工具；实际能力取决于所选模型。"""
    return get_llm(temperature).bind_tools(tools)


def clear_llm_cache() -> None:
    """供测试或运行时重新加载配置后清理模型缓存。"""
    get_llm.cache_clear()

"""
LangChain LLM factory — swap provider via LLM_PROVIDER env var.
Supported: anthropic (default), openai, gemini, ollama, azure
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """
    Input:  LLM_PROVIDER, MODEL_NAME, and provider-specific vars from environment
    Output: configured LangChain chat model ready for .invoke() / .ainvoke()

    For azure, MODEL_NAME is the deployment name. Required env vars:
      AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION
    """
    provider    = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model       = os.getenv("MODEL_NAME", _default_model(provider))
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    if provider == "azure":
        from langchain_openai import AzureChatOpenAI
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key  = os.getenv("AZURE_OPENAI_API_KEY")
        version  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT must be set when LLM_PROVIDER=azure")
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY must be set when LLM_PROVIDER=azure")
        return AzureChatOpenAI(
            azure_deployment=model,
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=version,
            temperature=temperature,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        f"Supported: anthropic, openai, azure, gemini, ollama"
    )


def _default_model(provider: str) -> str:
    defaults = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai":    "gpt-4o",
        "azure":     "gpt-4o",
        "gemini":    "gemini-2.0-flash",
        "ollama":    "gemma3:12b",
    }
    return defaults.get(provider, "claude-sonnet-4-20250514")

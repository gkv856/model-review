"""
LangChain LLM factory — swap provider via LLM_PROVIDER env var.
Supported: anthropic (default), openai, gemini, ollama
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """
    Input:  LLM_PROVIDER, MODEL_NAME, and API key from environment
    Output: configured LangChain chat model ready for .invoke() / .ainvoke()

    For ollama, set LLM_PROVIDER=ollama. No API key required.
    OLLAMA_BASE_URL defaults to http://localhost:11434.
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
        f"Unknown LLM_PROVIDER '{provider}'. Supported: anthropic, openai, gemini, ollama"
    )


def _default_model(provider: str) -> str:
    defaults = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai":    "gpt-4o",
        "gemini":    "gemini-2.0-flash",
        "ollama":    "gemma3:12b",
    }
    return defaults.get(provider, "claude-sonnet-4-20250514")

from .base import BaseLLM


def get_llm() -> BaseLLM:
    from config import (
        LLM_PROVIDER,
        OPENAI_API_KEY, OPENAI_MODEL,
        DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
    )

    if LLM_PROVIDER == "openai":
        from .openai_llm import OpenAILLM
        return OpenAILLM(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)

    if LLM_PROVIDER == "deepseek":
        from .deepseek_llm import DeepSeekLLM
        return DeepSeekLLM(api_key=DEEPSEEK_API_KEY, model=DEEPSEEK_MODEL)

    raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}. Choose from: openai, deepseek")

from .openai_llm import OpenAILLM


class DeepSeekLLM(OpenAILLM):
    """DeepSeek uses an OpenAI-compatible endpoint."""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(api_key=api_key, model=model, base_url="https://api.deepseek.com/v1")

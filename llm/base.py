from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """Return raw text completion."""
        ...

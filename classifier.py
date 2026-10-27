import json
import logging
from dataclasses import dataclass, field

from llm import get_llm, BaseLLM
from prompts import CLASSIFY_SYSTEM, CLASSIFY_USER
from i18n import AI_LANG_INSTRUCTION

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    relevant: bool
    score: int
    reason: str
    matched_interests: list[str]
    evidence: list[str] = field(default_factory=list)

    @classmethod
    def irrelevant(cls, reason: str = "Could not classify") -> "ClassificationResult":
        return cls(relevant=False, score=0, reason=reason, matched_interests=[])


class Classifier:
    def __init__(self, llm: BaseLLM | None = None):
        self._llm: BaseLLM | None = llm
        self._initialized = False

    def _ensure_llm(self):
        if self._llm is None:
            self._llm = get_llm()

    async def classify(
        self,
        message_text: str,
        interests: list[str],
        channel: str = "unknown",
        lang: str = "ru",
    ) -> ClassificationResult:
        if not interests:
            return ClassificationResult.irrelevant("No interests configured")
        if not message_text or not message_text.strip():
            return ClassificationResult.irrelevant("Empty message")

        self._ensure_llm()

        interests_str = "\n".join(f"- {i}" for i in interests)
        lang_instruction = AI_LANG_INSTRUCTION.get(lang, AI_LANG_INSTRUCTION["ru"])

        user_prompt = CLASSIFY_USER.format(
            interests=interests_str,
            channel=channel,
            message=message_text[:3000],
            lang_instruction=lang_instruction,
        )

        try:
            raw = await self._llm.complete(CLASSIFY_SYSTEM, user_prompt)
            result = self._parse(raw)
            logger.debug("Classified [%s] score=%s relevant=%s", channel, result.score, result.relevant)
            return result
        except Exception as exc:
            logger.error("LLM classification error: %s", exc)
            return ClassificationResult.irrelevant(f"LLM error: {exc}")

    @staticmethod
    def _parse(raw: str) -> ClassificationResult:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(text)
        return ClassificationResult(
            relevant=bool(data.get("relevant", False)),
            score=int(data.get("score", 0)),
            reason=str(data.get("reason", "")),
            matched_interests=list(data.get("matched_interests", [])),
        )

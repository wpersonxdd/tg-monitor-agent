"""Offline tests for the triage agent: a scripted fake LLM, a temporary SQLite DB, no Telegram or DeepSeek calls."""
import asyncio
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import database as db  # noqa: E402
import agent  # noqa: E402
from llm.base import BaseLLM  # noqa: E402


class ScriptedLLM(BaseLLM):
    """Returns canned replies in order; records the prompts it saw."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        return self.replies.pop(0)


class AgentTests(unittest.TestCase):
    USER = 4242
    CHANNEL = "@ai_news"

    @classmethod
    def setUpClass(cls):
        db.init_db()
        agent.ensure_tables()
        with db._get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO interests (user_id, interest, weight, created_at) VALUES (?,?,?,?)",
                         (cls.USER, "python", 1.5, "now"))
            conn.execute("INSERT INTO interactions (message_id, channel, user_id, feedback, score, timestamp) VALUES (1,?,?,?,80,'now')",
                         (cls.CHANNEL, cls.USER, "like"))
            conn.execute("INSERT INTO interactions (message_id, channel, user_id, feedback, score, timestamp) VALUES (2,?,?,?,40,'now')",
                         (cls.CHANNEL, cls.USER, "dislike"))

    def test_agent_calls_tools_and_returns_evidence(self):
        llm = ScriptedLLM([
            json.dumps({"tool": "interest_weights", "args": {}}),
            json.dumps({"tool": "channel_feedback", "args": {"channel": "whatever"}}),
            json.dumps({"final": {"relevant": True, "score": 85, "reason": "Про Python 3.13",
                                  "matched_interests": ["python"],
                                  "evidence": ["python weight 1.5", "channel liked 1, disliked 1"]}}),
        ])
        result = asyncio.run(agent.TriageAgent(llm=llm).classify(
            "Вышел Python 3.13 с новым GIL", ["python"], self.CHANNEL, "ru", self.USER, 99))

        self.assertTrue(result.relevant)
        self.assertEqual(result.score, 85)
        self.assertEqual(result.matched_interests, ["python"])
        self.assertEqual(len(result.evidence), 2)
        # The second tool result must carry the real channel, not the model's argument.
        self.assertIn('"likes": 1', llm.prompts[2])
        self.assertIn('"dislikes": 1', llm.prompts[2])

        trace = agent.get_trace(self.USER, self.CHANNEL, 99)
        self.assertIsNotNone(trace)
        self.assertEqual([s.get("tool") for s in trace["steps"][:2]], ["interest_weights", "channel_feedback"])
        self.assertTrue(trace["final"]["relevant"])

    def test_unknown_tool_is_reported_back_and_budget_forces_final(self):
        llm = ScriptedLLM([
            json.dumps({"tool": "delete_everything", "args": {}}),
            json.dumps({"tool": "past_matches", "args": {}}),
            json.dumps({"tool": "past_matches", "args": {}}),
            json.dumps({"final": {"relevant": False, "score": 10, "reason": "ad", "matched_interests": [], "evidence": []}}),
        ])
        result = asyncio.run(agent.TriageAgent(llm=llm).classify(
            "Buy crypto now!!!", ["python"], self.CHANNEL, "en", self.USER, 100))
        self.assertFalse(result.relevant)
        self.assertIn("unknown tool", llm.prompts[1])
        self.assertIn("Tool budget used", llm.prompts[3])

    def test_bad_json_falls_back_to_plain_classifier(self):
        llm = ScriptedLLM(["not json at all"])
        result = asyncio.run(agent.TriageAgent(llm=llm).classify(
            "post", ["python"], self.CHANNEL, "en", self.USER, 101))
        # Plain classifier also calls the LLM; the scripted LLM has no reply left, so it returns irrelevant.
        self.assertFalse(result.relevant)

    def test_no_interests_short_circuits(self):
        llm = ScriptedLLM([])
        result = asyncio.run(agent.TriageAgent(llm=llm).classify(
            "post", [], self.CHANNEL, "en", self.USER, 102))
        self.assertFalse(result.relevant)
        self.assertEqual(llm.prompts, [])


if __name__ == "__main__":
    unittest.main()

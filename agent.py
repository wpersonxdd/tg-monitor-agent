"""
Tool-using triage agent.

For each (post, user) pair the agent decides whether to notify the user.
Before deciding it may call read-only tools that query several data sources:
  - interest_weights:    what the user cares about and how much (interests table)
  - channel_feedback:    how this user has rated posts from this channel (interactions table)
  - past_matches:        earlier notifications with overlapping interests (sent_notifications table)

Every step is written to the agent_traces table, so the decision can be explained later.
"""
import json
import logging
from datetime import datetime, timezone

import database as db
from classifier import Classifier, ClassificationResult
from llm import get_llm, BaseLLM

logger = logging.getLogger(__name__)

MAX_TOOL_STEPS = 3

AGENT_SYSTEM = """You are a triage agent for a Telegram signal filter.
Decide whether a post is relevant to the user's interests. You may call tools to gather evidence first.
Reply with JSON only, in one of two forms:
  {"tool": "<tool name>", "args": {...}}
  {"final": {"relevant": true|false, "score": 0-100, "reason": "short reason in the requested language",
             "matched_interests": ["..."], "evidence": ["short facts from the tools or the post that support the decision"]}}
Tools:
  interest_weights() -> the user's interests with weights (0.1..2.0; higher = more important to the user)
  channel_feedback(channel) -> how many posts from this channel the user liked or disliked
  past_matches() -> the user's last notifications with the interests that matched
Call at most {max_steps} tools. Be strict with spam and ads. score >= 70 means relevant."""


def _tool_interest_weights(user_id: int, **_) -> dict:
    weights = db.get_interest_weights(user_id)
    return {"interests": weights}


def _tool_channel_feedback(user_id: int, channel: str = "", **_) -> dict:
    likes, dislikes = _channel_feedback_counts(user_id, channel)
    return {"channel": channel, "likes": likes, "dislikes": dislikes}


def _tool_past_matches(user_id: int, **_) -> dict:
    return {"recent": _recent_notifications(user_id, limit=10)}


TOOLS = {
    "interest_weights": _tool_interest_weights,
    "channel_feedback": _tool_channel_feedback,
    "past_matches": _tool_past_matches,
}


class TriageAgent:
    def __init__(self, llm: BaseLLM | None = None):
        self._llm = llm
        self._fallback = Classifier(llm=llm)

    def _ensure_llm(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    async def classify(
        self,
        message_text: str,
        interests: list[str],
        channel: str,
        lang: str,
        user_id: int,
        message_id: int,
    ) -> ClassificationResult:
        if not interests or not message_text.strip():
            return ClassificationResult.irrelevant("No interests or empty message")

        steps: list[dict] = []
        try:
            final = await self._run(message_text, interests, channel, lang, user_id, steps)
        except Exception as exc:
            logger.error("Agent failed, falling back to plain classifier: %s", exc)
            return await self._fallback.classify(message_text, interests, channel=channel, lang=lang)

        result = ClassificationResult(
            relevant=bool(final.get("relevant", False)),
            score=int(final.get("score", 0)),
            reason=str(final.get("reason", "")),
            matched_interests=list(final.get("matched_interests", [])),
            evidence=[str(e) for e in final.get("evidence", [])],
        )
        _save_trace(user_id, channel, message_id, steps, final)
        return result

    async def _run(self, text, interests, channel, lang, user_id, steps) -> dict:
        llm = self._ensure_llm()
        system = AGENT_SYSTEM.replace("{max_steps}", str(MAX_TOOL_STEPS))
        header = (
            f"Requested language for reason: {lang}\n"
            f"User interests: {', '.join(interests)}\n"
            f"Channel: @{channel}\n"
            f"Post:\n---\n{text[:3000]}\n---\n"
        )
        transcript = header

        for _ in range(MAX_TOOL_STEPS):
            raw = await llm.complete(system, transcript + "\nNext step (JSON only):")
            action = _parse_json(raw)
            if "final" in action:
                steps.append({"final": action["final"]})
                return action["final"]

            name = action.get("tool", "")
            args = action.get("args", {}) or {}
            if name not in TOOLS:
                observation = {"error": f"unknown tool {name!r}"}
            else:
                # The channel comes from the post being judged, not from the model's arguments.
                observation = TOOLS[name](user_id=user_id, channel=channel)
            steps.append({"tool": name, "args": args, "observation": observation})
            transcript += f"\nTool result {name}: {json.dumps(observation, ensure_ascii=False)}\n"

        raw = await llm.complete(system, transcript + "\nTool budget used. Reply with the final JSON now.")
        final = _parse_json(raw).get("final", {})
        steps.append({"final": final})
        return final


def _channel_feedback_counts(user_id: int, channel: str) -> tuple[int, int]:
    with db._get_conn() as conn:
        rows = conn.execute(
            "SELECT feedback, COUNT(*) AS n FROM interactions WHERE user_id=? AND channel=? GROUP BY feedback",
            (user_id, channel),
        ).fetchall()
    counts = {r["feedback"]: r["n"] for r in rows}
    return counts.get("like", 0), counts.get("dislike", 0)


def _recent_notifications(user_id: int, limit: int) -> list[dict]:
    with db._get_conn() as conn:
        rows = conn.execute(
            "SELECT channel, message_id, matched_interests, score FROM sent_notifications "
            "WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [
        {"channel": r["channel"], "score": r["score"], "matched_interests": json.loads(r["matched_interests"] or "[]")}
        for r in rows
    ]


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("agent reply is not a JSON object")
    return data


# ─── Storage for decision traces ──────────────────────────────────────────────

def ensure_tables():
    with db._get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                channel     TEXT NOT NULL,
                message_id  INTEGER NOT NULL,
                steps       TEXT NOT NULL,
                final       TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            )
        """)


def _save_trace(user_id: int, channel: str, message_id: int, steps: list, final: dict):
    try:
        ensure_tables()
        with db._get_conn() as conn:
            conn.execute(
                "INSERT INTO agent_traces (user_id, channel, message_id, steps, final, timestamp) VALUES (?,?,?,?,?,?)",
                (user_id, channel, message_id, json.dumps(steps, ensure_ascii=False),
                 json.dumps(final, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
            )
    except Exception as exc:
        logger.error("Could not save agent trace: %s", exc)


def get_trace(user_id: int, channel: str, message_id: int) -> dict | None:
    ensure_tables()
    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT steps, final, timestamp FROM agent_traces WHERE user_id=? AND channel=? AND message_id=? ORDER BY id DESC LIMIT 1",
            (user_id, channel, message_id),
        ).fetchone()
    if not row:
        return None
    return {"steps": json.loads(row["steps"]), "final": json.loads(row["final"]), "timestamp": row["timestamp"]}

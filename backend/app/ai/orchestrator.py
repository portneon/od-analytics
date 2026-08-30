"""Ask-Your-Data query flow (spec sections 48-52).

User question -> LLM tool-calling loop against approved analytics tools ->
structured result + narrative explanation. If no LLM provider is configured,
falls back to a deterministic keyword-routed tool call and returns the raw
data with an explicit note instead of fabricating a narrative -- the AI
degrades to "unavailable", it never invents an answer.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ai.provider import AIUnavailableError, ToolCallRecord, get_llm_provider
from app.ai.tools.definitions import TOOLS
from app.ai.tools.executor import build_executor
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are the AI Analyst for an Email Intelligence Platform. You help executives \
and analysts understand email delivery performance for ONE specific dataset.

Rules you must follow at all times:
- You may only state numbers/facts that came from a tool call result. Never invent or estimate a metric.
- If a tool returns no data or an error, say so plainly rather than guessing.
- Distinguish observed fact from inference. When explaining "why" something happened, use language like
  "associated with", "contributed to", or "coincided with" -- never "caused", unless a tool result
  explicitly establishes a controlled causal link (it will not, in this system).
- Prefer business language over technical jargon (e.g. say "recipient mailbox does not exist" rather
  than "SMTP 5.1.1"), but you may mention the technical code alongside it for analysts.
- When asked something outside what the tools can answer, say what data is unavailable rather than
  fabricating a plausible-sounding answer.
- Structure substantive answers as: Summary, What happened, Why (if applicable), Evidence, Affected
  entities, Recommended actions. Skip sections that don't apply to a simple question.
"""

_KEYWORD_TOOL_MAP: list[tuple[tuple[str, ...], str]] = [
    (("anomal", "unusual", "spike", "abnormal"), "get_anomalies"),
    (("bounce reason", "why bounc", "bounce categ"), "get_bounce_reasons"),
    (("domain",), "get_domain_metrics"),
    (("subject", "workflow", "application"), "get_subject_metrics"),
    (("sender",), "get_sender_metrics"),
    (("recipient", "problematic"), "get_recipient_metrics"),
    (("compare",), "compare_periods"),
    (("hour",), "get_hourly_metrics"),
    (("day", "trend", "timeline"), "get_daily_metrics"),
]


def _fallback_tool_and_args(question: str) -> tuple[str, dict]:
    lowered = question.lower()
    for keywords, tool_name in _KEYWORD_TOOL_MAP:
        if any(k in lowered for k in keywords):
            return tool_name, {}
    return "get_overview", {}


def ask_question(db: Session, *, dataset_id: uuid.UUID, question: str) -> dict:
    executor = build_executor(db, dataset_id)
    provider = get_llm_provider()

    try:
        result = provider.run_tool_loop(system_prompt=SYSTEM_PROMPT, user_message=question, tools=TOOLS, tool_executor=executor)
        return {
            "answer": result.final_text,
            "ai_available": True,
            "tool_calls": [_serialize_call(c) for c in result.tool_calls],
        }
    except AIUnavailableError:
        tool_name, args = _fallback_tool_and_args(question)
        data = executor(tool_name, args)
        return {
            "answer": (
                "AI narrative generation is unavailable because no LLM provider is configured "
                "(set LLM_PROVIDER and LLM_API_KEY). Showing the underlying data that best matches "
                "your question instead."
            ),
            "ai_available": False,
            "tool_calls": [_serialize_call(ToolCallRecord(tool_name=tool_name, arguments=args, result=data))],
        }
    except Exception as exc:  # noqa: BLE001 - surfaced as a structured failure, not a 500 with a stack trace
        logger.error("ai.ask.failed", error=str(exc))
        return {
            "answer": "The AI analyst hit an error while processing this question. Please try again or rephrase.",
            "ai_available": False,
            "tool_calls": [],
            "error": str(exc),
        }


def _serialize_call(call: ToolCallRecord) -> dict:
    return {"tool": call.tool_name, "arguments": call.arguments, "result": call.result}

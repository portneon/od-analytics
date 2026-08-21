"""LLM provider abstraction (spec section 5, 49, 81).

The AI layer must never be hard-coded to one vendor. Each provider
implements the same `run_tool_loop` contract: given a system prompt, a user
question, a set of tool schemas, and a tool executor callback, it drives the
provider's native tool-calling loop and returns the final natural-language
answer plus a full audit trail of every tool call actually made -- so the
API layer can guarantee every number in the answer traces back to a real
tool call against the database, never an LLM guess.

When no provider is configured (no API key), `NoOpProvider` raises
`AIUnavailableError` rather than fabricating a response; callers must
degrade to returning raw tool/analytics output with an explicit
"AI narrative unavailable" note (see app.ai.orchestrator).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_TOOL_ITERATIONS = 6
REQUEST_TIMEOUT_SECONDS = 30


class AIUnavailableError(Exception):
    """Raised when no LLM provider is configured. Callers must show an
    explicit "AI unavailable" state, never fabricate a response."""


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    result: Any


@dataclass
class ToolLoopResult:
    final_text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


ToolExecutor = Callable[[str, dict], Any]


class LLMProvider(ABC):
    @abstractmethod
    def run_tool_loop(
        self, *, system_prompt: str, user_message: str, tools: list[dict], tool_executor: ToolExecutor
    ) -> ToolLoopResult: ...


class NoOpProvider(LLMProvider):
    def run_tool_loop(self, *, system_prompt: str, user_message: str, tools: list[dict], tool_executor: ToolExecutor) -> ToolLoopResult:
        raise AIUnavailableError("No LLM provider is configured (LLM_PROVIDER=none or missing LLM_API_KEY)")


class AnthropicProvider(LLMProvider):
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def run_tool_loop(self, *, system_prompt: str, user_message: str, tools: list[dict], tool_executor: ToolExecutor) -> ToolLoopResult:
        anthropic_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools
        ]
        messages: list[dict] = [{"role": "user", "content": user_message}]
        calls: list[ToolCallRecord] = []

        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            for _ in range(MAX_TOOL_ITERATIONS):
                response = client.post(
                    self.API_URL,
                    headers=self._headers(),
                    json={
                        "model": self._model,
                        "max_tokens": 2000,
                        "system": system_prompt,
                        "messages": messages,
                        "tools": anthropic_tools,
                    },
                )
                response.raise_for_status()
                body = response.json()

                content_blocks = body.get("content", [])
                messages.append({"role": "assistant", "content": content_blocks})

                tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
                if not tool_use_blocks:
                    text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                    return ToolLoopResult(final_text=text, tool_calls=calls)

                tool_results = []
                for block in tool_use_blocks:
                    result = tool_executor(block["name"], block.get("input", {}))
                    calls.append(ToolCallRecord(tool_name=block["name"], arguments=block.get("input", {}), result=result))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(result, default=str),
                    })
                messages.append({"role": "user", "content": tool_results})

        return ToolLoopResult(final_text="I wasn't able to finish analyzing this within the allotted steps.", tool_calls=calls)


class OpenAIProvider(LLMProvider):
    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def run_tool_loop(self, *, system_prompt: str, user_message: str, tools: list[dict], tool_executor: ToolExecutor) -> ToolLoopResult:
        openai_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in tools
        ]
        messages: list[dict] = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
        calls: list[ToolCallRecord] = []

        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            for _ in range(MAX_TOOL_ITERATIONS):
                response = client.post(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}", "content-type": "application/json"},
                    json={"model": self._model, "messages": messages, "tools": openai_tools},
                )
                response.raise_for_status()
                body = response.json()
                message = body["choices"][0]["message"]
                messages.append(message)

                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    return ToolLoopResult(final_text=message.get("content") or "", tool_calls=calls)

                for tc in tool_calls:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = tool_executor(name, args)
                    calls.append(ToolCallRecord(tool_name=name, arguments=args, result=result))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, default=str),
                    })

        return ToolLoopResult(final_text="I wasn't able to finish analyzing this within the allotted steps.", tool_calls=calls)


class GroqProvider(OpenAIProvider):
    """Groq exposes an OpenAI-compatible chat-completions API, so this only
    overrides the endpoint -- the request/response shape is identical."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic" and settings.LLM_API_KEY:
        return AnthropicProvider(settings.LLM_API_KEY, settings.LLM_MODEL)
    if settings.LLM_PROVIDER == "openai" and settings.LLM_API_KEY:
        return OpenAIProvider(settings.LLM_API_KEY, settings.LLM_MODEL)
    if settings.LLM_PROVIDER == "groq" and settings.LLM_API_KEY:
        return GroqProvider(settings.LLM_API_KEY, settings.LLM_MODEL)
    return NoOpProvider()

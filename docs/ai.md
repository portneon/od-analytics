# AI Analyst

## Principle

```
DATABASE → ANALYTICS → FACTS → AI → EXPLANATION      (correct)
DATABASE → RAW DATA → LLM → GUESS                     (never this)
```

The AI is an analytics assistant, not a source of truth. It can only state numbers that
came back from a tool call; it never computes or estimates a metric itself.

## Provider abstraction

`app/ai/provider.py` defines `LLMProvider` with one method, `run_tool_loop`, backed by
raw HTTP calls (via `httpx`) to each provider's native tool-calling API:

- `AnthropicProvider` — Messages API with `tools`/`tool_use`
- `OpenAIProvider` — Chat Completions API with `tools`/function calling
- `NoOpProvider` — used when `LLM_PROVIDER=none` or no `LLM_API_KEY` is set; raises
  `AIUnavailableError` rather than fabricating a response

Selecting a provider is a config change (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`),
never a code change — no part of the platform is hard-coded to one vendor.

## Tools

`app/ai/tools/definitions.py` declares the exact tool set the LLM may call:
`get_overview`, `get_daily_metrics`, `get_hourly_metrics`, `get_recipient_metrics`,
`get_domain_metrics`, `get_subject_metrics`, `get_sender_metrics`, `get_bounce_reasons`,
`get_anomalies`, `get_recipient_profile`, `get_domain_profile`, `compare_periods`,
`search_email_events`, `get_application_metrics`.

`app/ai/tools/executor.py` binds each tool name to a real analytics/database call
**scoped to a `tenant_id`/`dataset_id` fixed at executor-creation time from the
authenticated request** — the LLM supplies only the declared arguments (sort order,
limit, filters, dates), never tenant or dataset identity. This is the mechanism that
makes cross-tenant leakage or SQL injection via the AI structurally impossible: the LLM
cannot express a query outside these fourteen functions, and none of them accept a
tenant/dataset override.

## Query flow

```
User question → LLM tool-calling loop → approved analytics tools → DB
              → structured tool results → LLM narrative (Summary/What/Why/Evidence/
                Affected entities/Recommended actions)
```

`app/ai/orchestrator.py`'s system prompt requires: every number traces to a tool
result; "why" explanations use "associated with"/"contributed to", never "caused"
(matching the root-cause module's language discipline); unavailable data is stated
plainly, never guessed around.

## Fallback without a configured provider

If no LLM is configured, `ask_question` catches `AIUnavailableError`, does simple
keyword-based intent routing (e.g. "domain" → `get_domain_metrics`, "anomaly" →
`get_anomalies`) to pick one relevant tool, and returns its raw result with an explicit
`ai_available: false` flag and a note that narrative generation is unavailable. The UI
surfaces this clearly rather than pretending the answer is AI-authored.

## Safety

- Tenant isolation is structural (see above), not a prompt instruction.
- The AI never executes arbitrary SQL — only the fourteen typed tool functions.
- System prompts and credentials are never echoed back to the client.
- Tool call results (including raw data) are shown to the user by design — this is
  explainability, not a leak, since the results are already scoped to that user's own
  tenant/dataset.

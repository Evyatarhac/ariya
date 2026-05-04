"""Unified gateway across AI providers — spec §9.

Now includes:
  - cost tracker (per agent + per project)
  - dynamic routing (by task complexity, context length, cost budget)
  - secondary fallback
  - streaming hook (callback)
"""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import AsyncIterator, Awaitable, Callable, Optional

from ariya.config import settings

log = logging.getLogger("ariya.gateway")


AGENT_MODELS: dict[str, dict[str, str]] = {
    "ARIYA":    {"primary": "claude-opus-4-7",  "secondary": "gpt-4o"},
    "SCOUT":    {"primary": "claude-sonnet-4-6","secondary": "gpt-4o"},
    "ARCHITECT":{"primary": "claude-opus-4-7",  "secondary": "gpt-4o"},
    "SENTINEL": {"primary": "claude-opus-4-7",  "secondary": "gpt-4o"},
    "FORGE-BE": {"primary": "claude-sonnet-4-6","secondary": "gpt-4o"},
    "FORGE-FE": {"primary": "claude-sonnet-4-6","secondary": "gpt-4o"},
    "PROBE":    {"primary": "claude-sonnet-4-6","secondary": "gpt-4o"},
    "GUARDIAN": {"primary": "claude-sonnet-4-6","secondary": "gpt-4o"},
    "PHOENIX":  {"primary": "claude-opus-4-7",  "secondary": "gpt-4o"},
}

# rough USD / 1M tokens (input/output) — kept conservative; update as prices change
PRICE: dict[str, tuple[float, float]] = {
    "claude-opus-4-7":  (15.0, 75.0),
    "claude-sonnet-4-6":(3.0,  15.0),
    "claude-haiku-4-5": (0.8,   4.0),
    "gpt-4o":           (2.5,  10.0),
    "gpt-4.1":          (2.0,   8.0),
    "gemini-2.5-pro":   (1.25,  5.0),
    "codestral-latest": (0.2,   0.6),
}

CHEAP_MODEL = "claude-haiku-4-5"
LARGE_CONTEXT_MODEL = "gemini-2.5-pro"


def _provider_for(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt", "o3", "o4")):
        return "openai"
    if model.startswith("gemini"):
        return "google"
    if model.startswith(("codestral", "mistral")):
        return "mistral"
    return "unknown"


class CostTracker:
    def __init__(self):
        self.by_agent: dict[str, float] = defaultdict(float)
        self.by_model: dict[str, float] = defaultdict(float)
        self.by_project: dict[str, float] = defaultdict(float)
        self.tokens_in = 0
        self.tokens_out = 0

    def record(self, *, agent: str, model: str, project: Optional[str],
               in_tokens: int, out_tokens: int) -> float:
        ip, op = PRICE.get(model, (5.0, 15.0))
        cost = (in_tokens / 1e6) * ip + (out_tokens / 1e6) * op
        self.by_agent[agent] += cost
        self.by_model[model] += cost
        if project:
            self.by_project[project] += cost
        self.tokens_in += in_tokens
        self.tokens_out += out_tokens
        return cost

    def snapshot(self) -> dict:
        return {
            "total_usd": round(sum(self.by_agent.values()), 4),
            "by_agent": {k: round(v, 4) for k, v in self.by_agent.items()},
            "by_model": {k: round(v, 4) for k, v in self.by_model.items()},
            "by_project": {k: round(v, 4) for k, v in self.by_project.items()},
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
        }


cost = CostTracker()

StreamCallback = Callable[[str], Awaitable[None]]


def select_model(agent_id: str, prompt: str, *, complexity: str = "auto",
                 cost_priority: bool = False) -> str:
    """Dynamic model routing per spec §9.3."""
    plen = len(prompt)
    if plen > 80_000:
        return LARGE_CONTEXT_MODEL
    if cost_priority or complexity == "low" or plen < 800:
        return CHEAP_MODEL
    if complexity == "high":
        return AGENT_MODELS.get(agent_id, {}).get("primary", settings.default_model)
    return AGENT_MODELS.get(agent_id, {}).get("primary", settings.default_model)


class ModelGateway:
    def __init__(self):
        self._anthropic = None
        self._openai = None

    def _ensure(self):
        if settings.anthropic_api_key and self._anthropic is None:
            try:
                from anthropic import AsyncAnthropic
                self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
            except Exception as e:
                log.warning("anthropic init failed: %s", e)
        if settings.openai_api_key and self._openai is None:
            try:
                from openai import AsyncOpenAI
                self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
            except Exception as e:
                log.warning("openai init failed: %s", e)

    async def complete(
        self,
        agent_id: str,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        complexity: str = "auto",
        cost_priority: bool = False,
        project_id: Optional[str] = None,
        on_token: Optional[StreamCallback] = None,
    ) -> str:
        self._ensure()
        if model is None:
            model = select_model(agent_id, prompt, complexity=complexity, cost_priority=cost_priority)
        provider = _provider_for(model)

        if settings.mock_mode or provider in ("google", "mistral", "unknown"):
            return await self._mock(agent_id, prompt, model, project_id, on_token)

        try:
            if provider == "anthropic" and self._anthropic:
                if on_token:
                    text_parts: list[str] = []
                    async with self._anthropic.messages.stream(
                        model=model, max_tokens=max_tokens,
                        system=system or "You are a senior engineer.",
                        messages=[{"role": "user", "content": prompt}],
                    ) as stream:
                        async for chunk in stream.text_stream:
                            text_parts.append(chunk)
                            await on_token(chunk)
                        msg = await stream.get_final_message()
                    text = "".join(text_parts)
                    cost.record(agent=agent_id, model=model, project=project_id,
                                in_tokens=msg.usage.input_tokens,
                                out_tokens=msg.usage.output_tokens)
                    return text
                msg = await self._anthropic.messages.create(
                    model=model, max_tokens=max_tokens,
                    system=system or "You are a senior engineer.",
                    messages=[{"role": "user", "content": prompt}],
                )
                cost.record(agent=agent_id, model=model, project=project_id,
                            in_tokens=msg.usage.input_tokens,
                            out_tokens=msg.usage.output_tokens)
                return "".join(b.text for b in msg.content if hasattr(b, "text"))

            if provider == "openai" and self._openai:
                resp = await self._openai.chat.completions.create(
                    model=model, max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system or "You are a senior engineer."},
                        {"role": "user", "content": prompt},
                    ],
                )
                u = resp.usage
                cost.record(agent=agent_id, model=model, project=project_id,
                            in_tokens=u.prompt_tokens if u else 0,
                            out_tokens=u.completion_tokens if u else 0)
                text = resp.choices[0].message.content or ""
                if on_token and text:
                    await on_token(text)
                return text

        except Exception as e:
            log.warning("%s call failed (%s) — falling back", provider, e)

        secondary = AGENT_MODELS.get(agent_id, {}).get("secondary")
        if secondary and secondary != model:
            return await self.complete(agent_id, prompt, system=system, model=secondary,
                                       max_tokens=max_tokens, project_id=project_id,
                                       on_token=on_token)
        return await self._mock(agent_id, prompt, model, project_id, on_token)

    async def _mock(self, agent_id: str, prompt: str, model: str,
                    project_id: Optional[str], on_token: Optional[StreamCallback]) -> str:
        head = (prompt.strip().splitlines() or ["(empty)"])[0][:140]
        text = (
            f"[MOCK::{agent_id}::{model}]\n"
            f"Acknowledged: {head}\n"
            "Set ANTHROPIC_API_KEY or OPENAI_API_KEY for real LLM calls."
        )
        # mock tokens for cost demo
        cost.record(agent=agent_id, model=model, project=project_id,
                    in_tokens=len(prompt) // 4, out_tokens=len(text) // 4)
        if on_token:
            await on_token(text)
        return text


gateway = ModelGateway()

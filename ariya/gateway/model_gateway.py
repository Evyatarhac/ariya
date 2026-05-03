"""Unified gateway across AI providers — spec §9.

Supports: anthropic, openai, mock. LiteLLM-style abstraction so agents are
provider-agnostic. If no API keys are present we fall back to a deterministic
MOCK provider so the whole pipeline still runs end-to-end.
"""
from __future__ import annotations
import logging
from typing import Optional

from ariya.config import settings

log = logging.getLogger("ariya.gateway")


# Default model assignments per agent (spec §9.4)
AGENT_MODELS: dict[str, dict[str, str]] = {
    "ARIYA":    {"primary": "claude-opus-4-7",  "secondary": "gpt-4o"},
    "SCOUT":    {"primary": "gemini-2.5-pro",   "secondary": "claude-sonnet-4-6"},
    "ARCHITECT":{"primary": "claude-opus-4-7",  "secondary": "gpt-4.1"},
    "SENTINEL": {"primary": "claude-opus-4-7",  "secondary": "gpt-4o"},
    "FORGE-BE": {"primary": "claude-sonnet-4-6","secondary": "codestral-latest"},
    "FORGE-FE": {"primary": "claude-sonnet-4-6","secondary": "gpt-4o"},
    "PROBE":    {"primary": "claude-sonnet-4-6","secondary": "gpt-4o"},
    "GUARDIAN": {"primary": "claude-sonnet-4-6","secondary": "codestral-latest"},
    "PHOENIX":  {"primary": "claude-opus-4-7",  "secondary": "gpt-4.1"},
}


def _provider_for(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gpt") or model.startswith("o3") or model.startswith("o4"):
        return "openai"
    if model.startswith("gemini"):
        return "google"  # not implemented yet — see FIXES.md
    if model.startswith("codestral") or model.startswith("mistral"):
        return "mistral"  # not implemented yet
    return "unknown"


class ModelGateway:
    """Single entry point. agent.complete(...) -> string."""

    def __init__(self):
        self._anthropic = None
        self._openai = None

    def _ensure_clients(self):
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
    ) -> str:
        self._ensure_clients()

        if model is None:
            model = AGENT_MODELS.get(agent_id, {}).get("primary", settings.default_model)
        provider = _provider_for(model)

        if settings.mock_mode or provider in ("google", "mistral", "unknown"):
            return self._mock(agent_id, prompt, model)

        try:
            if provider == "anthropic" and self._anthropic:
                msg = await self._anthropic.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system or "You are a senior engineer.",
                    messages=[{"role": "user", "content": prompt}],
                )
                return "".join(b.text for b in msg.content if hasattr(b, "text"))
            if provider == "openai" and self._openai:
                resp = await self._openai.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system or "You are a senior engineer."},
                        {"role": "user", "content": prompt},
                    ],
                )
                return resp.choices[0].message.content or ""
        except Exception as e:
            log.warning("%s call failed (%s) — falling back to mock", provider, e)
            return self._mock(agent_id, prompt, model)

        # secondary fallback path
        secondary = AGENT_MODELS.get(agent_id, {}).get("secondary")
        if secondary and secondary != model:
            return await self.complete(agent_id, prompt, system=system, model=secondary, max_tokens=max_tokens)
        return self._mock(agent_id, prompt, model)

    def _mock(self, agent_id: str, prompt: str, model: str) -> str:
        head = prompt.strip().splitlines()[0][:120] if prompt.strip() else "(empty)"
        return (
            f"[MOCK::{agent_id}::{model}]\n"
            f"Acknowledged task: {head}\n"
            f"Result: stub output. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY for real LLM calls."
        )


gateway = ModelGateway()

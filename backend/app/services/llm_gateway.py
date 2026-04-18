"""LLM Gateway — centralized orchestration for all LLM calls.

Every LLM call flows through the gateway:
  gateway.complete(prompt_slug, variables)
    → Prompt resolution (via PromptService)
    → Model routing (via AiRoutingRule)
    → Provider dispatch (Anthropic / OpenAI)
    → Cost calculation + request logging
    → Monthly spend tracking

Provides observability, cost control, and unified model management.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import anthropic
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_gateway import (
    AiModelConfig,
    AiMonthlySpend,
    AiRequestLog,
    AiRoutingRule,
)
from app.models.control_plane import AgentPrompt
from app.services.llm_service import get_api_key
from app.services.prompt_service import prompt_service

logger = logging.getLogger(__name__)


@dataclass
class GatewayResponse:
    """Normalized response from any LLM provider."""

    content: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    model: str
    provider: str
    finish_reason: str
    cost_usd: float
    latency_ms: int
    prompt_slug: str | None = None
    prompt_version_id: uuid.UUID | None = None


class LLMGateway:
    """Centralized LLM call routing with logging and cost tracking.

    Usage:
        gateway = LLMGateway()
        response = gateway.complete_sync(
            db=db,
            org_id=org_id,
            prompt_slug="portal-agent-system",
            variables={"story": story_text},
            source="agent",
        )
    """

    def complete_sync(
        self,
        db: Session,
        org_id: uuid.UUID,
        prompt_slug: str,
        variables: dict[str, Any] | None = None,
        label: str = "production",
        source: str | None = None,
        job_id: uuid.UUID | None = None,
        model_override: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        messages: list[dict] | None = None,
    ) -> GatewayResponse:
        """Execute an LLM call with full gateway orchestration (sync, for Celery workers).

        Args:
            db: Sync database session
            org_id: Organization ID for tenant isolation
            prompt_slug: Slug of the prompt to resolve
            variables: Template variables for Jinja2 rendering
            label: Deployment label (production, staging, canary)
            source: Call source for logging (agent, chat, control_plane)
            job_id: Associated agent job ID (if from an agent run)
            model_override: Force a specific model (bypasses routing)
            temperature: Override temperature
            max_tokens: Override max tokens
            messages: Additional messages to append after system prompt
        """
        start_time = time.monotonic()
        prompt_version_id = None

        # --- Step 1: Resolve and render prompt ---
        system_prompt = prompt_service.render_prompt_sync(
            db, org_id, prompt_slug, label, variables
        )

        if not system_prompt:
            # Fallback: try loading from markdown file
            system_prompt = self._load_fallback_prompt(prompt_slug)

        if not system_prompt:
            raise ValueError(f"No prompt found for slug '{prompt_slug}' (label={label})")

        # Get version ID for logging
        version = prompt_service.resolve_prompt_sync(db, org_id, prompt_slug, label)
        if version:
            prompt_version_id = version.id

        # --- Step 2: Resolve model ---
        model_config = self._resolve_model(db, org_id, prompt_slug, model_override)
        provider = model_config.provider if model_config else settings.default_llm_provider
        model_id = model_config.model_id if model_config else settings.default_model

        # --- Step 3: Merge parameters ---
        params = self._merge_params(model_config, prompt_slug, db, org_id, temperature, max_tokens)

        # --- Step 4: Build messages ---
        call_messages = [{"role": "user", "content": system_prompt}]
        if messages:
            call_messages.extend(messages)

        # --- Step 5: Dispatch to provider ---
        try:
            api_key = get_api_key(db, org_id, provider)
            result = self._call_provider(
                provider=provider,
                model=model_id,
                api_key=api_key,
                messages=call_messages,
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 4096),
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            self._log_request(
                db, org_id, prompt_slug, prompt_version_id,
                model_config, provider, model_id,
                0, 0, 0, 0.0, latency_ms,
                status="error", error_message=str(e),
                source=source, job_id=job_id,
            )
            raise

        # --- Step 6: Calculate cost ---
        cost_usd = self._calculate_cost(
            model_config,
            result["input_tokens"],
            result["output_tokens"],
            result.get("cached_input_tokens", 0),
        )
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # --- Step 7: Log request ---
        self._log_request(
            db, org_id, prompt_slug, prompt_version_id,
            model_config, provider, model_id,
            result["input_tokens"], result["output_tokens"],
            result.get("cached_input_tokens", 0),
            cost_usd, latency_ms,
            status="success", finish_reason=result.get("finish_reason"),
            source=source, job_id=job_id,
        )

        # --- Step 8: Update monthly spend ---
        self._update_monthly_spend(
            db, org_id, provider, model_id,
            result["input_tokens"], result["output_tokens"], cost_usd,
        )

        return GatewayResponse(
            content=result["content"],
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            cached_input_tokens=result.get("cached_input_tokens", 0),
            model=model_id,
            provider=provider,
            finish_reason=result.get("finish_reason", ""),
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            prompt_slug=prompt_slug,
            prompt_version_id=prompt_version_id,
        )

    # --- Provider dispatch ---

    def _call_provider(
        self,
        provider: str,
        model: str,
        api_key: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """Dispatch to the appropriate LLM provider."""
        if provider == "anthropic":
            return self._call_anthropic(model, api_key, messages, temperature, max_tokens)
        elif provider == "openai":
            return self._call_openai(model, api_key, messages, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _call_anthropic(
        self, model: str, api_key: str, messages: list[dict],
        temperature: float, max_tokens: int,
    ) -> dict:
        client = anthropic.Anthropic(api_key=api_key)

        # Extract system message if first message is system
        system_content = None
        chat_messages = messages
        if messages and messages[0].get("role") == "system":
            system_content = messages[0]["content"]
            chat_messages = messages[1:]

        # If only one user message, use it directly
        if not chat_messages:
            chat_messages = [{"role": "user", "content": "Please respond based on your instructions."}]

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_content:
            kwargs["system"] = system_content

        response = client.messages.create(**kwargs)

        return {
            "content": response.content[0].text if response.content else "",
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cached_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            "finish_reason": response.stop_reason or "",
        }

    def _call_openai(
        self, model: str, api_key: str, messages: list[dict],
        temperature: float, max_tokens: int,
    ) -> dict:
        try:
            import openai
        except ImportError:
            raise ImportError("openai package required for OpenAI provider. pip install openai")

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0] if response.choices else None
        usage = response.usage

        return {
            "content": choice.message.content if choice else "",
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "cached_input_tokens": 0,
            "finish_reason": choice.finish_reason if choice else "",
        }

    # --- Model resolution ---

    def _resolve_model(
        self, db: Session, org_id: uuid.UUID, prompt_slug: str,
        model_override: str | None = None,
    ) -> AiModelConfig | None:
        """Resolve which model to use via routing rules or override."""
        if model_override:
            result = db.execute(
                select(AiModelConfig).where(
                    AiModelConfig.organization_id == org_id,
                    AiModelConfig.slug == model_override,
                    AiModelConfig.is_active.is_(True),
                )
            )
            config = result.scalar_one_or_none()
            if config:
                return config

        # Get prompt metadata for routing
        prompt_result = db.execute(
            select(AgentPrompt).where(
                AgentPrompt.slug == prompt_slug,
                AgentPrompt.is_active.is_(True),
            )
        )
        prompt = prompt_result.scalar_one_or_none()

        # Evaluate routing rules in priority order
        rules_result = db.execute(
            select(AiRoutingRule)
            .where(
                AiRoutingRule.organization_id == org_id,
                AiRoutingRule.is_active.is_(True),
            )
            .order_by(AiRoutingRule.priority)
        )
        rules = rules_result.scalars().all()

        for rule in rules:
            if self._rule_matches(rule, prompt_slug, prompt):
                # Load the model config
                mc_result = db.execute(
                    select(AiModelConfig).where(
                        AiModelConfig.id == rule.model_config_id,
                        AiModelConfig.is_active.is_(True),
                    )
                )
                model_config = mc_result.scalar_one_or_none()
                if model_config:
                    return model_config

        return None  # Will fall back to env defaults

    @staticmethod
    def _rule_matches(
        rule: AiRoutingRule, prompt_slug: str, prompt: AgentPrompt | None,
    ) -> bool:
        """Check if a routing rule matches the current prompt."""
        if rule.match_prompt_slugs and prompt_slug in rule.match_prompt_slugs:
            return True
        if prompt and rule.match_category and rule.match_category == prompt.category:
            return True
        if prompt and rule.match_tags and prompt.tags:
            if set(rule.match_tags) & set(prompt.tags):
                return True
        return False

    # --- Parameter merging ---

    def _merge_params(
        self, model_config: AiModelConfig | None, prompt_slug: str,
        db: Session, org_id: uuid.UUID,
        temperature: float | None, max_tokens: int | None,
    ) -> dict:
        """Merge parameters: model defaults < prompt defaults < caller overrides."""
        merged: dict[str, Any] = {}

        # Layer 1: Model defaults
        if model_config and model_config.default_params:
            merged.update(model_config.default_params)

        # Layer 2: Prompt-level params
        prompt_result = db.execute(
            select(AgentPrompt).where(AgentPrompt.slug == prompt_slug)
        )
        prompt = prompt_result.scalar_one_or_none()
        if prompt and prompt.model_params:
            merged.update(prompt.model_params)

        # Layer 3: Caller overrides
        if temperature is not None:
            merged["temperature"] = temperature
        if max_tokens is not None:
            merged["max_tokens"] = max_tokens

        return merged

    # --- Cost calculation ---

    @staticmethod
    def _calculate_cost(
        model_config: AiModelConfig | None,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int,
    ) -> float:
        if not model_config:
            return 0.0

        regular_input = max(0, input_tokens - cached_input_tokens)
        cost = 0.0
        cost += model_config.cost_per_1k_input * (regular_input / 1000.0)
        cost += model_config.cost_per_1k_cached_input * (cached_input_tokens / 1000.0)
        cost += model_config.cost_per_1k_output * (output_tokens / 1000.0)
        return round(cost, 6)

    # --- Request logging ---

    def _log_request(
        self,
        db: Session, org_id: uuid.UUID,
        prompt_slug: str | None, prompt_version_id: uuid.UUID | None,
        model_config: AiModelConfig | None,
        provider: str, model: str,
        input_tokens: int, output_tokens: int, cached_input_tokens: int,
        cost_usd: float, latency_ms: int,
        status: str = "success", finish_reason: str | None = None,
        error_message: str | None = None,
        source: str | None = None, job_id: uuid.UUID | None = None,
    ) -> None:
        log = AiRequestLog(
            organization_id=org_id,
            prompt_slug=prompt_slug,
            prompt_version_id=prompt_version_id,
            model_config_id=model_config.id if model_config else None,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
            finish_reason=finish_reason,
            error_message=error_message,
            source=source,
            job_id=job_id,
        )
        db.add(log)
        try:
            db.flush()
        except Exception as e:
            logger.warning(f"Failed to log LLM request: {e}")

    # --- Monthly spend tracking ---

    def _update_monthly_spend(
        self, db: Session, org_id: uuid.UUID,
        provider: str, model: str,
        input_tokens: int, output_tokens: int, cost_usd: float,
    ) -> None:
        year_month = datetime.now(timezone.utc).strftime("%Y-%m")
        try:
            db.execute(text("""
                INSERT INTO ai_monthly_spend
                    (id, organization_id, year_month, provider, model,
                     total_requests, total_input_tokens, total_output_tokens,
                     total_cost_usd, total_errors, updated_at)
                VALUES
                    (gen_random_uuid(), :org_id, :year_month, :provider, :model,
                     1, :input_tokens, :output_tokens,
                     :cost_usd, 0, now())
                ON CONFLICT ON CONSTRAINT uq_ai_monthly_spend
                DO UPDATE SET
                    total_requests = ai_monthly_spend.total_requests + 1,
                    total_input_tokens = ai_monthly_spend.total_input_tokens + :input_tokens,
                    total_output_tokens = ai_monthly_spend.total_output_tokens + :output_tokens,
                    total_cost_usd = ai_monthly_spend.total_cost_usd + :cost_usd,
                    updated_at = now()
            """), {
                "org_id": str(org_id), "year_month": year_month,
                "provider": provider, "model": model,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            })
            db.flush()
        except Exception as e:
            logger.warning(f"Failed to update monthly spend: {e}")

    # --- Fallback prompts ---

    @staticmethod
    def _load_fallback_prompt(slug: str) -> str | None:
        """Try to load a prompt from markdown files as fallback."""
        import os
        prompts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "agents", "prompts",
        )
        # Convert slug to filename: "portal-agent-system" → "portal_agent.md"
        filename = slug.replace("-agent-system", "_agent").replace("-", "_") + ".md"
        filepath = os.path.join(prompts_dir, filename)
        if os.path.exists(filepath):
            with open(filepath) as f:
                return f.read()
        return None


# Singleton
llm_gateway = LLMGateway()

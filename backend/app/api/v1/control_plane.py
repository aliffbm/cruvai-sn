"""AI Control Plane API — manage prompts, versions, labels, and skills.

Endpoints for both the admin UI and remote OpenClaw instances.
"""

import difflib
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.control_plane import (
    AgentPrompt,
    AgentPromptLabel,
    AgentPromptVersion,
    AgentSkill,
    AgentSkillStep,
)
from app.models.ai_gateway import (
    AiModelConfig,
    AiRoutingRule,
    AiRequestLog,
    AiMonthlySpend,
)
from app.services.prompt_service import prompt_service

router = APIRouter()


# === Schemas ===

class PromptCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None
    agent_type: str | None = None
    category: str = "system"
    tags: list[str] | None = None
    template_format: str = "jinja2"
    default_variables: dict | None = None
    model_params: dict | None = None
    content: str  # Initial template content (creates version 1)


class PromptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_type: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    default_variables: dict | None = None
    model_params: dict | None = None
    is_active: bool | None = None


class PromptResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    agent_type: str | None
    category: str
    tags: list | None
    template_format: str
    default_variables: dict | None
    model_params: dict | None
    is_system: bool
    is_active: bool
    labels: list[dict] | None = None
    latest_version_number: int | None = None

    model_config = {"from_attributes": True}


class VersionCreate(BaseModel):
    content: str
    change_notes: str | None = None
    sections: dict | None = None
    variables_schema: dict | None = None


class VersionResponse(BaseModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    version_number: int
    content: str
    content_hash: str
    sections: dict | None
    variables_schema: dict | None
    change_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LabelSet(BaseModel):
    version_id: uuid.UUID
    label: str = "production"


class LabelResponse(BaseModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    label: str
    version_id: uuid.UUID
    traffic_weight: int
    is_active: bool
    activated_at: datetime | None

    model_config = {"from_attributes": True}


class RenderRequest(BaseModel):
    variables: dict[str, Any] | None = None
    label: str = "production"


class RenderResponse(BaseModel):
    rendered: str
    version_number: int
    content_hash: str
    slug: str


class SkillCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None
    agent_type: str | None = None
    pre_conditions: dict | None = None
    post_conditions: dict | None = None
    is_composite: bool = False


class SkillResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    agent_type: str | None
    pre_conditions: dict | None
    post_conditions: dict | None
    is_composite: bool
    is_system: bool
    is_active: bool
    steps: list[dict] | None = None

    model_config = {"from_attributes": True}


class SkillStepData(BaseModel):
    step_number: int
    name: str
    description: str | None = None
    step_type: str  # tool_call, llm_call, sub_skill, conditional, loop
    tool_name: str | None = None
    sub_skill_id: uuid.UUID | None = None
    prompt_slug: str | None = None
    input_mapping: dict | None = None
    output_mapping: dict | None = None
    condition: dict | None = None
    retry_policy: dict | None = None
    is_approval_gate: bool = False


# === Prompt Endpoints ===

@router.get("/prompts", response_model=list[PromptResponse])
async def list_prompts(
    agent_type: str | None = None,
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    query = select(AgentPrompt).where(
        AgentPrompt.is_active.is_(True),
        AgentPrompt.deleted_at.is_(None),
        # Show org-specific + system prompts
        (AgentPrompt.organization_id == org_id) | (AgentPrompt.organization_id.is_(None)),
    ).options(selectinload(AgentPrompt.labels))

    if agent_type:
        query = query.where(AgentPrompt.agent_type == agent_type)
    if category:
        query = query.where(AgentPrompt.category == category)
    if search:
        query = query.where(AgentPrompt.name.ilike(f"%{search}%"))

    result = await db.execute(query.order_by(AgentPrompt.name))
    prompts = result.scalars().all()

    responses = []
    for p in prompts:
        labels = [{"label": l.label, "version_id": str(l.version_id), "is_active": l.is_active} for l in p.labels]
        # Get latest version number
        ver_result = await db.execute(
            select(func.max(AgentPromptVersion.version_number))
            .where(AgentPromptVersion.prompt_id == p.id)
        )
        latest_ver = ver_result.scalar()

        responses.append(PromptResponse(
            id=p.id, slug=p.slug, name=p.name, description=p.description,
            agent_type=p.agent_type, category=p.category, tags=p.tags,
            template_format=p.template_format, default_variables=p.default_variables,
            model_params=p.model_params, is_system=p.is_system, is_active=p.is_active,
            labels=labels, latest_version_number=latest_ver,
        ))
    return responses


@router.post("/prompts", response_model=PromptResponse, status_code=201)
async def create_prompt(
    req: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    prompt = AgentPrompt(
        organization_id=current_user.organization_id,
        slug=req.slug,
        name=req.name,
        description=req.description,
        agent_type=req.agent_type,
        category=req.category,
        tags=req.tags,
        template_format=req.template_format,
        default_variables=req.default_variables,
        model_params=req.model_params,
    )
    db.add(prompt)
    await db.flush()

    # Create version 1
    version = await prompt_service.create_version(
        db, prompt.id, req.content, "Initial version", user_id=current_user.id
    )

    # Create production label pointing to version 1
    await prompt_service.promote_version(
        db, prompt.id, version.id, "production", current_user.id
    )

    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.get("/prompts/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AgentPrompt)
        .where(AgentPrompt.id == prompt_id)
        .options(selectinload(AgentPrompt.labels))
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if prompt.organization_id and prompt.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Prompt not found")

    labels = [{"label": l.label, "version_id": str(l.version_id), "is_active": l.is_active} for l in prompt.labels]
    ver_result = await db.execute(
        select(func.max(AgentPromptVersion.version_number))
        .where(AgentPromptVersion.prompt_id == prompt.id)
    )
    return PromptResponse(
        id=prompt.id, slug=prompt.slug, name=prompt.name, description=prompt.description,
        agent_type=prompt.agent_type, category=prompt.category, tags=prompt.tags,
        template_format=prompt.template_format, default_variables=prompt.default_variables,
        model_params=prompt.model_params, is_system=prompt.is_system, is_active=prompt.is_active,
        labels=labels, latest_version_number=ver_result.scalar(),
    )


@router.patch("/prompts/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: uuid.UUID,
    req: PromptUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(select(AgentPrompt).where(AgentPrompt.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt or (prompt.organization_id and prompt.organization_id != org_id):
        raise HTTPException(status_code=404, detail="Prompt not found")
    if prompt.is_system:
        raise HTTPException(status_code=403, detail="Cannot edit system prompts. Fork it by creating a new prompt with the same slug.")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(prompt, field, value)
    await db.commit()
    await db.refresh(prompt)
    return prompt


# === Version Endpoints ===

@router.post("/prompts/{prompt_id}/versions", response_model=VersionResponse, status_code=201)
async def create_version(
    prompt_id: uuid.UUID,
    req: VersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    version = await prompt_service.create_version(
        db, prompt_id, req.content, req.change_notes, req.sections, req.variables_schema, current_user.id
    )
    await db.commit()
    return version


@router.get("/prompts/{prompt_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AgentPromptVersion)
        .where(AgentPromptVersion.prompt_id == prompt_id)
        .order_by(AgentPromptVersion.version_number.desc())
    )
    return result.scalars().all()


@router.get("/prompts/{prompt_id}/diff")
async def diff_versions(
    prompt_id: uuid.UUID,
    v1: uuid.UUID,
    v2: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    r1 = await db.execute(select(AgentPromptVersion).where(AgentPromptVersion.id == v1))
    r2 = await db.execute(select(AgentPromptVersion).where(AgentPromptVersion.id == v2))
    ver1 = r1.scalar_one_or_none()
    ver2 = r2.scalar_one_or_none()
    if not ver1 or not ver2:
        raise HTTPException(status_code=404, detail="Version not found")

    diff = list(difflib.unified_diff(
        ver1.content.splitlines(keepends=True),
        ver2.content.splitlines(keepends=True),
        fromfile=f"v{ver1.version_number}",
        tofile=f"v{ver2.version_number}",
    ))
    return {"diff": "".join(diff), "v1": ver1.version_number, "v2": ver2.version_number}


# === Label Endpoints ===

@router.post("/prompts/{prompt_id}/labels", response_model=LabelResponse)
async def set_label(
    prompt_id: uuid.UUID,
    req: LabelSet,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    label = await prompt_service.promote_version(
        db, prompt_id, req.version_id, req.label, current_user.id
    )
    await db.commit()
    await db.refresh(label)
    return label


@router.get("/prompts/{prompt_id}/labels", response_model=list[LabelResponse])
async def list_labels(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentPromptLabel).where(AgentPromptLabel.prompt_id == prompt_id)
    )
    return result.scalars().all()


# === Render Endpoint (for agents and OpenClaw) ===

@router.post("/prompts/{slug}/render", response_model=RenderResponse)
async def render_prompt(
    slug: str,
    req: RenderRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Render a prompt template. Used by local agents and remote OpenClaw instances."""
    version = await prompt_service.resolve_prompt(db, org_id, slug, req.label)
    if not version:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found or no '{req.label}' label")

    rendered = await prompt_service.render_prompt(db, org_id, slug, req.label, req.variables)
    return RenderResponse(
        rendered=rendered,
        version_number=version.version_number,
        content_hash=version.content_hash,
        slug=slug,
    )


# === Skill Endpoints ===

@router.get("/skills", response_model=list[SkillResponse])
async def list_skills(
    agent_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    query = select(AgentSkill).where(
        AgentSkill.is_active.is_(True),
        AgentSkill.deleted_at.is_(None),
        (AgentSkill.organization_id == org_id) | (AgentSkill.organization_id.is_(None)),
    ).options(selectinload(AgentSkill.steps))
    if agent_type:
        query = query.where(AgentSkill.agent_type == agent_type)

    result = await db.execute(query.order_by(AgentSkill.name))
    skills = result.scalars().all()

    responses = []
    for s in skills:
        steps = [
            {"step_number": st.step_number, "name": st.name, "step_type": st.step_type,
             "tool_name": st.tool_name, "prompt_slug": st.prompt_slug,
             "is_approval_gate": st.is_approval_gate}
            for st in s.steps
        ]
        responses.append(SkillResponse(
            id=s.id, slug=s.slug, name=s.name, description=s.description,
            agent_type=s.agent_type, pre_conditions=s.pre_conditions,
            post_conditions=s.post_conditions, is_composite=s.is_composite,
            is_system=s.is_system, is_active=s.is_active, steps=steps,
        ))
    return responses


@router.post("/skills", response_model=SkillResponse, status_code=201)
async def create_skill(
    req: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    skill = AgentSkill(
        organization_id=current_user.organization_id,
        slug=req.slug,
        name=req.name,
        description=req.description,
        agent_type=req.agent_type,
        pre_conditions=req.pre_conditions,
        post_conditions=req.post_conditions,
        is_composite=req.is_composite,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AgentSkill)
        .where(AgentSkill.id == skill_id)
        .options(selectinload(AgentSkill.steps))
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    steps = [
        {"step_number": st.step_number, "name": st.name, "step_type": st.step_type,
         "tool_name": st.tool_name, "prompt_slug": st.prompt_slug,
         "is_approval_gate": st.is_approval_gate, "id": str(st.id),
         "input_mapping": st.input_mapping, "output_mapping": st.output_mapping}
        for st in skill.steps
    ]
    return SkillResponse(
        id=skill.id, slug=skill.slug, name=skill.name, description=skill.description,
        agent_type=skill.agent_type, pre_conditions=skill.pre_conditions,
        post_conditions=skill.post_conditions, is_composite=skill.is_composite,
        is_system=skill.is_system, is_active=skill.is_active, steps=steps,
    )


@router.put("/skills/{skill_id}/steps")
async def replace_skill_steps(
    skill_id: uuid.UUID,
    steps: list[SkillStepData],
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Replace all steps for a skill (atomic update)."""
    # Delete existing steps
    result = await db.execute(select(AgentSkillStep).where(AgentSkillStep.skill_id == skill_id))
    for step in result.scalars().all():
        await db.delete(step)

    # Insert new steps
    for step_data in steps:
        step = AgentSkillStep(
            skill_id=skill_id,
            **step_data.model_dump(),
        )
        db.add(step)

    await db.commit()
    return {"detail": f"Replaced {len(steps)} steps"}


# === Model Config Endpoints ===

class ModelConfigCreate(BaseModel):
    slug: str
    display_name: str
    provider: str
    model_id: str
    capabilities: dict | None = None
    default_params: dict | None = None
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    cost_per_1k_cached_input: float = 0.0
    fallback_model_id: uuid.UUID | None = None


class ModelConfigUpdate(BaseModel):
    display_name: str | None = None
    capabilities: dict | None = None
    default_params: dict | None = None
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    cost_per_1k_cached_input: float | None = None
    fallback_model_id: uuid.UUID | None = None
    is_active: bool | None = None


@router.get("/models")
async def list_models(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AiModelConfig)
        .where(AiModelConfig.organization_id == org_id, AiModelConfig.deleted_at.is_(None))
        .order_by(AiModelConfig.provider, AiModelConfig.slug)
    )
    return [_model_response(m) for m in result.scalars().all()]


@router.post("/models", status_code=201)
async def create_model(
    req: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    model = AiModelConfig(organization_id=org_id, **req.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _model_response(model)


@router.put("/models/{model_id}")
async def update_model(
    model_id: uuid.UUID,
    req: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AiModelConfig).where(AiModelConfig.id == model_id, AiModelConfig.organization_id == org_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, "Model not found")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    await db.commit()
    await db.refresh(model)
    return _model_response(model)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AiModelConfig).where(AiModelConfig.id == model_id, AiModelConfig.organization_id == org_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, "Model not found")
    model.deleted_at = datetime.now(timezone.utc)
    await db.commit()


def _model_response(m: AiModelConfig) -> dict:
    return {
        "id": str(m.id), "slug": m.slug, "display_name": m.display_name,
        "provider": m.provider, "model_id": m.model_id,
        "capabilities": m.capabilities, "default_params": m.default_params,
        "cost_per_1k_input": m.cost_per_1k_input,
        "cost_per_1k_output": m.cost_per_1k_output,
        "cost_per_1k_cached_input": m.cost_per_1k_cached_input,
        "fallback_model_id": str(m.fallback_model_id) if m.fallback_model_id else None,
        "is_active": m.is_active,
    }


# === Routing Rule Endpoints ===

class RoutingRuleCreate(BaseModel):
    name: str
    description: str | None = None
    priority: int = 100
    match_category: str | None = None
    match_tags: list[str] | None = None
    match_prompt_slugs: list[str] | None = None
    model_config_id: uuid.UUID


@router.get("/routing-rules")
async def list_routing_rules(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AiRoutingRule)
        .where(AiRoutingRule.organization_id == org_id, AiRoutingRule.deleted_at.is_(None))
        .order_by(AiRoutingRule.priority)
    )
    rules = result.scalars().all()
    return [
        {
            "id": str(r.id), "name": r.name, "description": r.description,
            "priority": r.priority, "match_category": r.match_category,
            "match_tags": r.match_tags, "match_prompt_slugs": r.match_prompt_slugs,
            "model_config_id": str(r.model_config_id), "is_active": r.is_active,
        }
        for r in rules
    ]


@router.post("/routing-rules", status_code=201)
async def create_routing_rule(
    req: RoutingRuleCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    rule = AiRoutingRule(organization_id=org_id, **req.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id": str(rule.id), "name": rule.name, "priority": rule.priority}


@router.delete("/routing-rules/{rule_id}", status_code=204)
async def delete_routing_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AiRoutingRule).where(AiRoutingRule.id == rule_id, AiRoutingRule.organization_id == org_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Routing rule not found")
    rule.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# === Request Logs Endpoint ===

@router.get("/logs")
async def list_request_logs(
    limit: int = 50,
    prompt_slug: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    query = select(AiRequestLog).where(
        AiRequestLog.organization_id == org_id
    )
    if prompt_slug:
        query = query.where(AiRequestLog.prompt_slug == prompt_slug)
    if provider:
        query = query.where(AiRequestLog.provider == provider)
    if status:
        query = query.where(AiRequestLog.status == status)

    query = query.order_by(AiRequestLog.created_at.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": str(l.id), "created_at": l.created_at.isoformat(),
            "prompt_slug": l.prompt_slug, "provider": l.provider,
            "model": l.model, "input_tokens": l.input_tokens,
            "output_tokens": l.output_tokens, "cost_usd": float(l.cost_usd),
            "latency_ms": l.latency_ms, "status": l.status,
            "finish_reason": l.finish_reason, "error_message": l.error_message,
            "source": l.source,
        }
        for l in logs
    ]


# === Spend Endpoint ===

@router.get("/spend")
async def list_monthly_spend(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AiMonthlySpend)
        .where(AiMonthlySpend.organization_id == org_id)
        .order_by(AiMonthlySpend.year_month.desc())
        .limit(12)
    )
    rows = result.scalars().all()
    return [
        {
            "year_month": s.year_month, "provider": s.provider, "model": s.model,
            "total_requests": s.total_requests, "total_input_tokens": s.total_input_tokens,
            "total_output_tokens": s.total_output_tokens,
            "total_cost_usd": float(s.total_cost_usd), "total_errors": s.total_errors,
            "budget_limit_usd": float(s.budget_limit_usd) if s.budget_limit_usd else None,
        }
        for s in rows
    ]

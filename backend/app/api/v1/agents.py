import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.agent import AgentDefinition

router = APIRouter()


class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    agent_type: str
    default_model: str
    requires_approval: bool
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.is_active.is_(True))
    )
    return result.scalars().all()

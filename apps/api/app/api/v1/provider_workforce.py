from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_permissions
from app.domains.auth.models import User
from app.domains.workforce.provider_team import ProviderTeamService
from app.domains.workforce.schemas import (
    ProviderWorkerCreate,
    ProviderWorkerList,
    ProviderWorkerRead,
)

router = APIRouter()
team_read = require_permissions("provider.profile.read")
team_manage = require_permissions("provider.worker.manage")


@router.get("", response_model=ProviderWorkerList)
async def list_provider_workers(
    user: Annotated[User, Depends(team_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderWorkerList:
    return await ProviderTeamService(session).list_workers(user)


@router.post("", response_model=ProviderWorkerRead, status_code=status.HTTP_201_CREATED)
async def create_provider_worker(
    command: ProviderWorkerCreate,
    user: Annotated[User, Depends(team_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderWorkerRead:
    return await ProviderTeamService(session).add_worker(user, command)

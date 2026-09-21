import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.access_service import AccessService
from app.domains.auth.dependencies import current_user, require_permissions
from app.domains.auth.models import AccessRole, Department, TenantScope, User
from app.domains.auth.schemas import AccessProfileUpdate, PortalContext

router = APIRouter()
admin_only = require_permissions("admin.access.manage")
BrandKey = Annotated[
    str,
    Query(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$"),
]


@router.get("/me", response_model=PortalContext)
async def current_access_context(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    brand_key: BrandKey = "breero",
) -> PortalContext:
    return await AccessService(session).context(user, brand_key)


@router.get("/catalog")
async def access_catalog(_: Annotated[User, Depends(admin_only)]) -> dict[str, list[str]]:
    return {
        "roles": [role.value for role in AccessRole],
        "departments": [department.value for department in Department],
        "tenant_scopes": [scope.value for scope in TenantScope],
    }


@router.get("/users/{user_id}", response_model=PortalContext)
async def user_access(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
    brand_key: BrandKey = "breero",
) -> PortalContext:
    target = await session.scalar(select(User).where(User.id == user_id))
    if not target:
        raise HTTPException(404, "User not found")
    return await AccessService(session).context(target, brand_key)


@router.put("/users/{user_id}", response_model=PortalContext)
async def replace_user_access(
    user_id: uuid.UUID,
    data: AccessProfileUpdate,
    actor: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortalContext:
    if any(item.role == AccessRole.superadmin for item in data.assignments):
        actor_context = await AccessService(session).context(actor, data.brand_key)
        if "*" not in actor_context.permissions:
            raise HTTPException(403, "Only superadmin can grant the superadmin role")
    return await AccessService(session).replace_assignments(
        user_id=user_id,
        brand_key=data.brand_key,
        assignments=data.assignments,
    )

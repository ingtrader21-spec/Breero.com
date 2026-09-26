import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.admin_schemas import (
    AdminUserAccessUpdate,
    AdminUserDetail,
    AdminUserLifecycleCommand,
    AdminUserList,
    AdminUserStatus,
    EffectiveAccess,
)
from app.domains.auth.admin_user_service import AdminUserService
from app.domains.auth.dependencies import require_permissions
from app.domains.auth.models import AccessRole, User, UserRole
from app.domains.auth.provisioning_service import (
    InternalUserProvisioningService,
)
from app.domains.auth.schemas import (
    InternalUserProvisionRequest,
    InternalUserProvisionResponse,
)

router = APIRouter()
can_provision_internal_user = require_permissions("admin.access.manage")
can_manage_users = require_permissions("admin.access.manage")
BrandKey = Annotated[
    str,
    Query(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$"),
]


def _correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


@router.post(
    "",
    response_model=InternalUserProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_internal_user(
    data: InternalUserProvisionRequest,
    actor: Annotated[User, Depends(can_provision_internal_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InternalUserProvisionResponse:
    return await InternalUserProvisioningService(session).provision(
        actor=actor,
        data=data,
    )


@router.get("", response_model=AdminUserList)
async def list_admin_users(
    _: Annotated[User, Depends(can_manage_users)],
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = Query(default=None, min_length=1, max_length=160),
    role: UserRole | None = Query(default=None),
    user_status: AdminUserStatus | None = Query(default=None, alias="status"),
    access_role: AccessRole | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> AdminUserList:
    return await AdminUserService(session).list_users(
        q=q,
        role=role,
        status=user_status,
        access_role=access_role,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=AdminUserDetail)
async def get_admin_user(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(can_manage_users)],
    session: Annotated[AsyncSession, Depends(get_db)],
    brand_key: BrandKey = "breero",
) -> AdminUserDetail:
    return await AdminUserService(session).detail(user_id, brand_key)


@router.get("/{user_id}/effective-access", response_model=EffectiveAccess)
async def get_admin_user_effective_access(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(can_manage_users)],
    session: Annotated[AsyncSession, Depends(get_db)],
    brand_key: BrandKey = "breero",
) -> EffectiveAccess:
    return await AdminUserService(session).effective_access(user_id, brand_key)


@router.put("/{user_id}/access", response_model=EffectiveAccess)
async def replace_admin_user_access(
    user_id: uuid.UUID,
    data: AdminUserAccessUpdate,
    request: Request,
    actor: Annotated[User, Depends(can_manage_users)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EffectiveAccess:
    return await AdminUserService(session).replace_access(
        actor, user_id, data, correlation_id=_correlation_id(request)
    )


@router.post("/{user_id}/disable", response_model=AdminUserDetail)
async def disable_admin_user(
    user_id: uuid.UUID,
    data: AdminUserLifecycleCommand,
    request: Request,
    actor: Annotated[User, Depends(can_manage_users)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserDetail:
    return await AdminUserService(session).disable(
        actor, user_id, data.reason, correlation_id=_correlation_id(request)
    )


@router.post("/{user_id}/reactivate", response_model=AdminUserDetail)
async def reactivate_admin_user(
    user_id: uuid.UUID,
    data: AdminUserLifecycleCommand,
    request: Request,
    actor: Annotated[User, Depends(can_manage_users)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserDetail:
    return await AdminUserService(session).reactivate(
        actor, user_id, data.reason, correlation_id=_correlation_id(request)
    )

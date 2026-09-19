import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.common.outbox import AuditLog
from app.domains.workforce.models import ProviderCredential
from app.domains.workforce.repository import WorkforceRepository
from app.domains.workforce.schemas import ProviderCredentialRead, ProviderCredentialWrite

router = APIRouter()


@router.put(
    "/vendors/{vendor_id}/credentials/{credential_type}/{jurisdiction}",
    response_model=ProviderCredentialRead,
)
async def upsert_provider_credential(
    vendor_id: uuid.UUID,
    credential_type: str,
    jurisdiction: str,
    payload: ProviderCredentialWrite,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    normalized_jurisdiction = jurisdiction.upper()
    if (
        payload.credential_type.value != credential_type.upper()
        or payload.jurisdiction.upper() != normalized_jurisdiction
    ):
        raise HTTPException(422, "Credential path and payload must match")

    vendor = await WorkforceRepository(session).get_vendor(vendor_id, lock=True)
    if not vendor:
        raise HTTPException(404, "Vendor not found")

    credential = await session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.vendor_id == vendor_id,
            ProviderCredential.credential_type == payload.credential_type,
            ProviderCredential.jurisdiction == normalized_jurisdiction,
        )
    )
    if credential is None:
        credential = ProviderCredential(
            vendor_id=vendor_id,
            credential_type=payload.credential_type,
            jurisdiction=normalized_jurisdiction,
            expires_on=payload.expires_on,
        )
        session.add(credential)

    credential.reference_last4 = payload.reference_last4
    credential.expires_on = payload.expires_on
    credential.verified = payload.verified
    credential.verified_at = datetime.now(UTC) if payload.verified else None
    credential.verified_by = user.id if payload.verified else None
    session.add(
        AuditLog(
            actor_id=user.id,
            actor_type="user",
            action="provider_credential.update",
            resource_type="vendor",
            resource_id=vendor_id,
            metadata_json={
                "credential_type": payload.credential_type.value,
                "jurisdiction": normalized_jurisdiction,
                "verified": payload.verified,
                "expires_on": payload.expires_on.isoformat(),
            },
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    await session.refresh(credential)
    return credential

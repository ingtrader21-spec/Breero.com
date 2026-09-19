import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.common.outbox import AuditLog
from app.domains.public_submissions.models import PublicSubmission
from app.domains.public_submissions.schemas import (
    DispatcherAuditEntry,
    DispatcherQueueItem,
    DispatcherQueueUpdate,
)

router = APIRouter()


@router.get("/dispatcher/queue", response_model=list[DispatcherQueueItem])
async def dispatcher_queue(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
) -> list[DispatcherQueueItem]:
    submissions = list(
        (
            await session.scalars(
                select(PublicSubmission)
                .order_by(PublicSubmission.created_at.asc())
                .limit(500)
            )
        ).all()
    )
    submission_ids = [item.id for item in submissions]
    audits = (
        list(
            (
                await session.scalars(
                    select(AuditLog)
                    .where(
                        AuditLog.resource_type == "public_submission",
                        AuditLog.resource_id.in_(submission_ids),
                    )
                    .order_by(AuditLog.created_at.asc())
                )
            ).all()
        )
        if submission_ids
        else []
    )
    audits_by_request: dict[uuid.UUID, list[DispatcherAuditEntry]] = {}
    for audit in audits:
        audits_by_request.setdefault(audit.resource_id, []).append(
            DispatcherAuditEntry(
                action=audit.action,
                actor_id=audit.actor_id,
                metadata=audit.metadata_json,
                created_at=audit.created_at,
            )
        )

    now = datetime.now(UTC)
    result: list[DispatcherQueueItem] = []
    for submission in submissions:
        payload = submission.payload
        created_at = submission.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        manual_state = payload.get("manual_dispatch_state")
        provider_assigned = payload.get("provider_assigned") is True
        contact_attempts = payload.get("contact_attempts") or []
        required_follow_up_value = payload.get("required_follow_up")
        required_follow_up = (
            required_follow_up_value
            if isinstance(required_follow_up_value, bool)
            else submission.submission_type.value != "SERVICE_REQUEST"
            or manual_state == "PENDING_MANUAL_DISPATCH"
            or not provider_assigned
        )
        result.append(
            DispatcherQueueItem(
                request_id=submission.id,
                submission_type=submission.submission_type.value,
                created_at=created_at,
                request_age_seconds=max(0, int((now - created_at).total_seconds())),
                required_follow_up=required_follow_up,
                customer_timezone=payload.get("customer_timezone"),
                address_verification_state=payload.get("geoapify_verification_state"),
                manual_dispatch_state=manual_state,
                provider_assigned=provider_assigned,
                contact_attempts=contact_attempts,
                downstream_status=submission.downstream_status.value,
                payload=payload,
                audit_history=audits_by_request.get(submission.id, []),
            )
        )
    return result


@router.patch(
    "/dispatcher/queue/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_dispatcher_queue_item(
    request_id: uuid.UUID,
    update: DispatcherQueueUpdate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
) -> None:
    submission = await session.scalar(
        select(PublicSubmission)
        .where(PublicSubmission.id == request_id)
        .with_for_update()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Service request not found")

    changes = update.model_dump(exclude_none=True)
    payload = dict(submission.payload)
    if "manual_dispatch_state" in changes:
        payload["manual_dispatch_state"] = changes["manual_dispatch_state"]
    if "address_verification_state" in changes:
        payload["geoapify_verification_state"] = changes["address_verification_state"]
    if "address_timezone" in changes:
        payload["address_timezone"] = changes["address_timezone"]
    if "required_follow_up" in changes:
        payload["required_follow_up"] = changes["required_follow_up"]
    if "contact_outcome" in changes:
        attempts = list(payload.get("contact_attempts") or [])
        attempts.append(
            {
                "outcome": changes["contact_outcome"],
                "note": changes.get("note"),
                "actor_id": str(user.id),
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        payload["contact_attempts"] = attempts
    submission.payload = payload
    session.add(
        AuditLog(
            actor_id=user.id,
            actor_type="user",
            action="manual_dispatch.update",
            resource_type="public_submission",
            resource_id=submission.id,
            metadata_json={key: value for key, value in changes.items() if key != "note"},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()

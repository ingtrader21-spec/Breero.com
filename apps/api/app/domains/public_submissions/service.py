import hashlib
import json
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import DomainError
from app.domains.catalog.models import Service
from app.domains.common.outbox import EventStatus, IntegrationEvent

from .consent import CONSENT_FLAGS, canonical_disclosures
from .models import DownstreamStatus, PublicSubmission, SubmissionType
from .schemas import SubmissionAccepted, TrackingFields


class PublicSubmissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _existing(
        self,
        submission_type: SubmissionType,
        idempotency_key: str,
    ) -> PublicSubmission | None:
        return await self.session.scalar(
            select(PublicSubmission).where(
                PublicSubmission.submission_type == submission_type,
                PublicSubmission.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def _replay_or_conflict(
        existing: PublicSubmission,
        request_hash: str,
    ) -> SubmissionAccepted:
        if existing.request_hash != request_hash:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT",
                "Key already used for another request",
                409,
            )
        return SubmissionAccepted(
            request_id=existing.id,
            downstream_status=existing.downstream_status.value,
        )

    async def _validate_service_request(self, payload: dict) -> None:
        service_id = payload.get("service_id")
        service_slug = payload.get("service_slug")
        service_filter = Service.id == service_id if service_id else Service.slug == service_slug
        service = await self.session.scalar(
            select(Service).where(service_filter, Service.is_active.is_(True))
        )
        if not service:
            raise DomainError("SERVICE_NOT_FOUND", "Selected service is not available", 422)

        payload["service_id"] = str(service.id)
        payload["service_slug"] = service.slug
        payload.update(
            {
                "request_status": "REQUESTED",
                "manual_dispatch_state": "PENDING_MANUAL_DISPATCH",
                "geoapify_verification_state": (
                    "PENDING_MANUAL_VALIDATION"
                    if not settings.geocoding_enabled
                    else "PENDING_PROVIDER_VERIFICATION"
                ),
                "address_timezone": None,
                "address_timezone_state": "PENDING_MANUAL_CALCULATION",
                "contact_attempts": [],
                "required_follow_up": True,
                "payment_required": False,
                "quote_required": True,
                "provider_assigned": False,
                "appointment_confirmed": False,
            }
        )

    async def _validate_provider_interest(self, payload: dict) -> None:
        categories = list(payload.get("service_categories") or [])
        active = set(
            await self.session.scalars(
                select(Service.slug).where(
                    Service.slug.in_(categories),
                    Service.is_active.is_(True),
                )
            )
        )
        unavailable = sorted(set(categories) - active)
        if unavailable:
            raise DomainError(
                "SERVICE_NOT_FOUND",
                "One or more selected services are not available",
                422,
            )

    async def accept(
        self,
        submission_type: SubmissionType,
        data: TrackingFields,
        idempotency_key: str,
        source_ip: str,
    ) -> SubmissionAccepted:
        if data.company:
            raise DomainError("SUBMISSION_REJECTED", "Submission could not be accepted", 400)
        if not data.transactional_contact_allowed:
            raise DomainError(
                "CONTACT_PERMISSION_REQUIRED",
                "Permission to contact you about this request is required",
                422,
            )

        client_payload = data.model_dump(mode="json", exclude={"company"})
        request_hash = hashlib.sha256(
            json.dumps(client_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        existing = await self._existing(submission_type, idempotency_key)
        if existing:
            return self._replay_or_conflict(existing, request_hash)

        now = datetime.now(UTC)
        payload = dict(client_payload)
        policy_version = str(payload["policy_version"])
        consent_flags = {flag: bool(payload.get(flag)) for flag in CONSENT_FLAGS}
        payload["client_consent_timestamp"] = payload.get("consent_timestamp")
        payload["client_consent_source"] = payload.get("consent_source")
        payload["client_consent_disclosures"] = dict(
            payload.get("consent_disclosures") or {}
        )
        payload["consent_timestamp"] = now.isoformat()
        payload["consent_source"] = "breero_public_api"
        payload["policy_version"] = policy_version
        payload["consent_disclosures"] = canonical_disclosures(
            consent_flags,
            policy_version,
        )
        payload["consent_recorded_by"] = "breero_api"

        if submission_type == SubmissionType.SERVICE_REQUEST:
            await self._validate_service_request(payload)
        elif submission_type == SubmissionType.PROVIDER_INTEREST:
            await self._validate_provider_interest(payload)

        email = str(payload["email"]).strip().lower()
        phone = re.sub(r"[^0-9+]", "", str(payload.get("phone") or "")) or None
        downstream = (
            DownstreamStatus.PENDING
            if settings.middleware_enabled
            else DownstreamStatus.PENDING_CONFIGURATION
        )
        submission = PublicSubmission(
            submission_type=submission_type,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            normalized_email=email,
            normalized_phone=phone,
            payload=payload,
            downstream_status=downstream,
            source_ip_hash=hashlib.sha256(source_ip.encode()).hexdigest(),
        )

        try:
            async with self.session.begin_nested():
                self.session.add(submission)
                await self.session.flush()
        except IntegrityError:
            raced = await self._existing(submission_type, idempotency_key)
            if raced is None:
                raise
            return self._replay_or_conflict(raced, request_hash)

        self.session.add(
            IntegrationEvent(
                aggregate_type="public_submission",
                aggregate_id=submission.id,
                event_type={
                    SubmissionType.SERVICE_REQUEST: "breero.service_request.created",
                    SubmissionType.CONTACT: "breero.contact_request.created",
                    SubmissionType.PROVIDER_INTEREST: "breero.provider_interest.created",
                }[submission_type],
                aggregate_version=1,
                schema_version=1,
                idempotency_key=f"{submission_type.value.lower()}:{submission.id}:1",
                payload={
                    "submission_id": str(submission.id),
                    "route": submission_type.value,
                    "payload": payload,
                },
                status=(
                    EventStatus.PENDING
                    if settings.middleware_enabled
                    else EventStatus.PENDING_CONFIGURATION
                ),
                next_attempt_at=now,
                processed_at=None,
            )
        )
        await self.session.commit()
        return SubmissionAccepted(request_id=submission.id, downstream_status=downstream.value)

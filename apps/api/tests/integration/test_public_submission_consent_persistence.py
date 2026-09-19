import uuid

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.domains.common.outbox import IntegrationEvent
from app.domains.public_submissions.consent import (
    CONSENT_DISCLOSURES_BY_POLICY,
    DEFAULT_CONSENT_POLICY_VERSION,
)
from app.domains.public_submissions.models import PublicSubmission, SubmissionType
from app.domains.public_submissions.schemas import ContactCreate
from app.domains.public_submissions.service import PublicSubmissionService


@pytest.mark.asyncio
async def test_public_submission_persists_server_owned_consent_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "middleware_enabled", False)
    marker = uuid.uuid4().hex
    client_text = "Client-supplied text must never become the canonical disclosure."
    contact = ContactCreate(
        name="Consent persistence customer",
        email=f"consent-{marker}@example.com",
        category="general",
        subject="Consent persistence",
        message="This request proves the server-owned consent record.",
        source_url="https://breero.com/contact",
        transactional_contact_allowed=True,
        transactional_sms_consent=True,
        policy_version=DEFAULT_CONSENT_POLICY_VERSION,
        consent_disclosures={"transactional_sms": client_text},
        consent_source="breero_public_intake",
    )

    async with SessionLocal() as session:
        accepted = await PublicSubmissionService(session).accept(
            SubmissionType.CONTACT,
            contact,
            f"consent-persistence-{marker}",
            "192.0.2.90",
        )
        submission = await session.get(PublicSubmission, accepted.request_id)
        event = await session.scalar(
            select(IntegrationEvent).where(IntegrationEvent.aggregate_id == accepted.request_id)
        )

    assert submission is not None
    assert event is not None
    expected_sms = CONSENT_DISCLOSURES_BY_POLICY[DEFAULT_CONSENT_POLICY_VERSION][
        "transactional_sms"
    ]
    assert submission.payload["policy_version"] == DEFAULT_CONSENT_POLICY_VERSION
    assert submission.payload["consent_disclosures"] == {
        "transactional_contact": CONSENT_DISCLOSURES_BY_POLICY[DEFAULT_CONSENT_POLICY_VERSION]["transactional_contact"],
        "transactional_sms": expected_sms,
    }
    assert submission.payload["client_consent_disclosures"] == {
        "transactional_sms": client_text
    }
    assert submission.payload["consent_disclosures"]["transactional_sms"] != client_text
    assert submission.payload["consent_recorded_by"] == "breero_api"
    assert submission.payload["consent_timestamp"]
    assert event.payload["payload"]["consent_disclosures"] == submission.payload[
        "consent_disclosures"
    ]

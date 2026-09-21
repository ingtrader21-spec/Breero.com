import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import (
    EmailVerificationToken,
    PasswordResetToken,
    PhoneVerificationToken,
    Session,
    User,
    UserRole,
)
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import (
    LoginRequest,
    ProviderRegisterRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.domains.auth.security import (
    REFRESH_TOKEN_TTL_SECONDS,
    TOKEN_TTL_SECONDS,
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
    verify_password_and_update,
)
from app.domains.booking.models import Address, Booking, Customer, ProviderServiceCoverage
from app.domains.booking.timezones import timezone
from app.domains.catalog.models import Service
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.common.us import US_STATES_AND_DC
from app.domains.workforce.models import Vendor, VendorStatus, Worker, WorkerStatus
from app.domains.workforce.provider_models import ProviderService, ProviderServiceArea


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def register(
        self, data: RegisterRequest, user_agent: str | None = None, ip: str | None = None
    ) -> TokenResponse:
        email = data.email.lower()
        if await self.users.by_email(email):
            raise HTTPException(status_code=409, detail="Email already registered")
        try:
            user = await self.users.add(
                User(
                    email=email,
                    phone=data.phone,
                    full_name=data.full_name.strip(),
                    password_hash=await hash_password(data.password),
                    role=UserRole.customer,
                )
            )
            await self._link_customer(user)
            self.session.add(
                AuditLog(
                    actor_id=user.id,
                    actor_type="user",
                    action="client.created",
                    resource_type="user",
                    resource_id=user.id,
                    metadata_json={},
                    created_at=datetime.now(UTC),
                )
            )
            await self._issue_verification(user)
            if user.phone:
                await self._issue_phone_verification(user)
            token = await self._tokens(user, user_agent, ip)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Email already registered") from exc
        await self.session.refresh(user)
        token.user = UserRead.model_validate(user)
        return token

    async def register_provider(
        self,
        data: ProviderRegisterRequest,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> tuple[TokenResponse, Vendor]:
        email = str(data.email).strip().lower()
        state_code = data.state.strip().upper()
        if state_code not in US_STATES_AND_DC:
            raise HTTPException(422, "A valid U.S. state or DC is required")
        timezone(data.timezone_id)
        postal_codes = sorted({postal.split("-", 1)[0] for postal in data.service_postal_codes})
        if any(len(postal) != 5 or not postal.isdigit() for postal in postal_codes):
            raise HTTPException(422, "Service ZIP codes must contain five digits")
        services = list(
            (
                await self.session.scalars(
                    select(Service).where(
                        Service.slug.in_(set(data.service_slugs)), Service.is_active.is_(True)
                    )
                )
            ).all()
        )
        if len(services) != len(set(data.service_slugs)):
            raise HTTPException(422, "Provider services must use active BREERO catalog entries")
        if await self.users.by_email(email):
            raise HTTPException(409, "Account already registered")
        try:
            user = await self.users.add(
                User(
                    email=email,
                    phone=data.phone,
                    full_name=data.contact_name.strip(),
                    password_hash=await hash_password(data.password),
                    role=UserRole.vendor_admin,
                )
            )
            vendor = Vendor(
                legal_name=data.legal_name.strip(),
                display_name=data.display_name.strip(),
                provider_type=data.provider_type,
                email=email,
                phone=data.phone,
                business_address=data.business_address.strip(),
                city=data.city.strip(),
                state=state_code,
                postal_code=data.postal_code,
                timezone_id=data.timezone_id,
                status=VendorStatus.PENDING,
                onboarding_status="PENDING",
                compliance_status="PENDING",
                owner_user_id=user.id,
                capabilities=sorted({service.slug for service in services}),
            )
            self.session.add(vendor)
            await self.session.flush()
            names = data.contact_name.strip().split(maxsplit=1)
            worker = Worker(
                vendor_id=vendor.id,
                user_id=user.id,
                first_name=names[0],
                last_name=names[1] if len(names) > 1 else "",
                email=email,
                phone=data.phone,
                status=WorkerStatus.INVITED,
                available=False,
                default_timezone_id=data.timezone_id,
                skills=sorted({service.slug for service in services}),
            )
            self.session.add(worker)
            await self.session.flush()
            self.session.add_all(
                ProviderServiceCoverage(
                    worker_id=worker.id,
                    service_id=service.id,
                    postal_code=postal_code,
                    active=False,
                )
                for service in services
                for postal_code in postal_codes
            )
            self.session.add_all(
                ProviderService(
                    provider_id=vendor.id,
                    service_id=service.id,
                    active=False,
                    approval_status="PENDING",
                )
                for service in services
            )
            self.session.add_all(
                ProviderServiceArea(
                    provider_id=vendor.id,
                    professional_id=worker.id,
                    area_type="ZIP",
                    postal_code=postal_code,
                    state=state_code,
                    active=False,
                    approval_status="PENDING",
                )
                for postal_code in postal_codes
            )
            self.session.add(
                AuditLog(
                    actor_id=user.id,
                    actor_type="user",
                    action="provider.registered",
                    resource_type="vendor",
                    resource_id=vendor.id,
                    metadata_json={"status": "PENDING", "service_count": len(services)},
                    created_at=datetime.now(UTC),
                )
            )
            await self._issue_verification(user)
            await self._issue_phone_verification(user)
            token = await self._tokens(user, user_agent, ip)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Account or provider already registered") from exc
        await self.session.refresh(user)
        await self.session.refresh(vendor)
        token.user = UserRead.model_validate(user)
        return token, vendor

    async def login(
        self, data: LoginRequest, user_agent: str | None = None, ip: str | None = None
    ) -> TokenResponse:
        user = await self.users.by_email(data.email.lower())
        valid_password = False
        updated_password_hash: str | None = None
        if user:
            valid_password, updated_password_hash = await verify_password_and_update(
                data.password,
                user.password_hash,
            )
        if not user or not valid_password or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        if updated_password_hash is not None:
            user.password_hash = updated_password_hash
        token = await self._tokens(user, user_agent, ip)
        user.last_login_at = datetime.now(UTC)
        self._audit(
            actor_id=user.id,
            actor_type="user",
            action="auth.login",
            resource_type="user",
            resource_id=user.id,
            metadata={
                "user_agent_present": bool(user_agent),
                "ip_present": bool(ip),
                "password_rehashed": updated_password_hash is not None,
            },
        )
        await self.session.commit()
        return token

    async def application_session(
        self, user: User, user_agent: str | None = None, ip: str | None = None
    ) -> TokenResponse:
        token = await self._tokens(user, user_agent, ip)
        user.last_login_at = datetime.now(UTC)
        await self.session.commit()
        return token


    async def refresh(
        self, raw_token: str, user_agent: str | None = None, ip: str | None = None
    ) -> TokenResponse:
        now = datetime.now(UTC)
        old = await self.users.session_by_hash(hash_token(raw_token), lock=True)
        if not old:
            raise HTTPException(401, "Invalid refresh token")
        if old.revoked_at or old.rotated_at:
            await self._revoke_family(old.family_id, now)
            await self.session.commit()
            raise HTTPException(401, "Refresh token reuse detected")
        if old.expires_at <= now:
            old.revoked_at = now
            await self.session.commit()
            raise HTTPException(401, "Refresh token expired")
        user = await self.users.by_id(old.user_id)
        if not user or not user.is_active:
            raise HTTPException(401, "Invalid refresh token")
        old.rotated_at = now
        response = await self._tokens(
            user, user_agent or old.user_agent, ip or old.ip_address, old.family_id
        )
        await self.session.commit()
        return response

    async def logout(self, raw_token: str) -> None:
        record = await self.users.session_by_hash(hash_token(raw_token), lock=True)
        if record and not record.revoked_at:
            record.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def logout_all(self, user: User) -> None:
        await self.session.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.commit()

    async def forgot_password(self, email: str) -> None:
        user = await self.users.by_email(email.lower())
        if user and user.is_active:
            raw = new_opaque_token()
            self.session.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=hash_token(raw),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            self._event(user, "password_reset_requested", {"token": raw})
            await self.session.commit()

    async def reset_password(self, raw: str, password: str) -> None:
        token = await self.users.reset_by_hash(hash_token(raw))
        now = datetime.now(UTC)
        if not token or token.used_at or token.expires_at <= now:
            raise HTTPException(400, "Invalid or expired reset token")
        user = await self.users.by_id(token.user_id)
        if not user:
            raise HTTPException(400, "Invalid or expired reset token")
        token.used_at = now
        await self._set_password(user, password, now, action="auth.password.reset")

    async def change_password(
        self,
        user: User,
        current: str,
        new: str,
    ) -> None:
        if not await verify_password(current, user.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        await self._set_password(
            user,
            new,
            datetime.now(UTC),
            action="auth.password.change",
        )

    async def set_initial_password(
        self,
        user: User,
        new: str,
    ) -> None:
        if not user.password_set_required:
            raise HTTPException(409, "Account password is already set")
        user.password_set_required = False
        await self._set_password(
            user,
            new,
            datetime.now(UTC),
            action="auth.password.set",
        )


    async def verify_email(self, raw: str) -> None:
        token = await self.users.verification_by_hash(hash_token(raw))
        now = datetime.now(UTC)
        if not token or token.used_at or token.expires_at <= now:
            raise HTTPException(400, "Invalid or expired verification token")
        user = await self.users.by_id(token.user_id)
        if not user:
            raise HTTPException(400, "Invalid or expired verification token")
        token.used_at = now
        user.email_verified = True
        user.email_verified_at = now
        await self._link_customer(user)
        await self.session.commit()

    async def resend_verification(self, user: User) -> None:
        if not user.email_verified:
            await self._issue_verification(user)
            await self.session.commit()

    async def verify_phone(self, user: User, raw: str) -> None:
        token = await self.users.phone_verification_by_hash(hash_token(raw))
        now = datetime.now(UTC)
        if not token or token.user_id != user.id or token.used_at or token.expires_at <= now:
            raise HTTPException(400, "Invalid or expired phone verification token")
        token.used_at = now
        user.phone_verified_at = now
        self.session.add(
            AuditLog(
                actor_id=user.id,
                actor_type="user",
                action="phone.verified",
                resource_type="user",
                resource_id=user.id,
                metadata_json={},
                created_at=now,
            )
        )
        await self.session.commit()

    async def _set_password(
        self,
        user: User,
        password: str,
        now: datetime,
        *,
        action: str,
    ) -> None:
        user.password_hash = await hash_password(password)
        user.credential_version += 1
        await self.session.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        self._event(user, "password_changed", {"reason": action})
        self._audit(
            actor_id=user.id,
            actor_type="user",
            action=action,
            resource_type="user",
            resource_id=user.id,
            metadata={"sessions_revoked": True},
        )
        await self.session.commit()

    async def _tokens(
        self, user: User, agent: str | None, ip: str | None, family: uuid.UUID | None = None
    ) -> TokenResponse:
        raw = new_opaque_token()
        self.session.add(
            Session(
                user_id=user.id,
                token_hash=hash_token(raw),
                family_id=family or uuid.uuid4(),
                user_agent=agent,
                ip_address=ip,
                expires_at=datetime.now(UTC) + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS),
            )
        )
        await self.session.flush()
        return TokenResponse(
            access_token=create_access_token(
                user.id, user.role.value, credential_version=user.credential_version
            ),
            expires_in=TOKEN_TTL_SECONDS,
            refresh_token=raw,
            refresh_expires_in=REFRESH_TOKEN_TTL_SECONDS,
            user=UserRead.model_validate(user),
        )

    async def _revoke_family(self, family: uuid.UUID, now: datetime) -> None:
        await self.session.execute(
            update(Session)
            .where(Session.family_id == family, Session.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def _issue_verification(self, user: User) -> None:
        raw = new_opaque_token()
        self.session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        self._event(user, "email_verification_requested", {"token": raw})

    async def _issue_phone_verification(self, user: User) -> None:
        if not user.phone:
            return
        raw = new_opaque_token()
        self.session.add(
            PhoneVerificationToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        )
        self._event(user, "phone_verification_requested", {"token": raw})

    async def _link_customer(self, user: User) -> None:
        customer = await self.session.scalar(
            select(Customer)
            .where(Customer.email == user.email, Customer.user_id.is_(None))
            .order_by(Customer.created_at)
            .limit(1)
            .with_for_update()
        )
        if customer:
            customer.user_id = user.id
        else:
            parts = user.full_name.split(maxsplit=1)
            customer = Customer(
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else "",
                email=user.email,
                phone="",
                user_id=user.id,
            )
            self.session.add(customer)
            await self.session.flush()
        await self.session.execute(
            update(Address)
            .where(
                Address.customer_id.is_(None),
                Address.id.in_(
                    select(Booking.address_id).where(Booking.customer_id == customer.id)
                ),
            )
            .values(customer_id=customer.id)
        )

    def _event(self, user: User, event_type: str, payload: dict[str, str]) -> None:
        self.session.add(
            IntegrationEvent(
                aggregate_type="user",
                aggregate_id=user.id,
                event_type=event_type,
                payload={"user_id": str(user.id), "email": user.email, **payload},
                status=EventStatus.PENDING,
                attempts=0,
                available_at=datetime.now(UTC),
            )
        )

    def _audit(
        self,
        *,
        actor_id: uuid.UUID | None,
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        metadata: dict,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                actor_type=actor_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json=metadata,
                created_at=datetime.now(UTC),
            )
        )

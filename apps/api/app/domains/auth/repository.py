import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import (
    AccountInvitationToken,
    EmailVerificationToken,
    IdentityLink,
    PasswordResetToken,
    PhoneVerificationToken,
    Session,
    User,
)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(User.email == email.lower())
        )

    async def by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def by_keycloak_subject(self, issuer: str, subject: str) -> User | None:
        return await self.session.scalar(
            select(User).where(User.keycloak_issuer == issuer, User.keycloak_subject == subject)
        )

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def identity_by_subject(
        self,
        brand_key: str,
        issuer: str,
        subject: str,
    ) -> IdentityLink | None:
        return await self.session.scalar(
            select(IdentityLink).where(
                IdentityLink.brand_key == brand_key,
                IdentityLink.issuer == issuer,
                IdentityLink.subject == subject,
            )
        )

    async def identity_by_user_issuer(
        self,
        brand_key: str,
        issuer: str,
        user_id: uuid.UUID,
    ) -> IdentityLink | None:
        return await self.session.scalar(
            select(IdentityLink).where(
                IdentityLink.brand_key == brand_key,
                IdentityLink.issuer == issuer,
                IdentityLink.user_id == user_id,
            )
        )

    async def add_identity(self, identity: IdentityLink) -> IdentityLink:
        self.session.add(identity)
        await self.session.flush()
        return identity

    async def session_by_hash(
        self,
        token_hash: str,
        *,
        lock: bool = False,
    ) -> Session | None:
        query = select(Session).where(Session.token_hash == token_hash)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def reset_by_hash(
        self,
        token_hash: str,
    ) -> PasswordResetToken | None:
        return await self.session.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
        )

    async def verification_by_hash(
        self,
        token_hash: str,
    ) -> EmailVerificationToken | None:
        return await self.session.scalar(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token_hash == token_hash)
            .with_for_update()
        )

    async def phone_verification_by_hash(self, token_hash: str) -> PhoneVerificationToken | None:
        return await self.session.scalar(
            select(PhoneVerificationToken).where(PhoneVerificationToken.token_hash == token_hash)
        )

    async def invitation_by_hash(
        self,
        token_hash: str,
    ) -> AccountInvitationToken | None:
        return await self.session.scalar(
            select(AccountInvitationToken)
            .where(AccountInvitationToken.token_hash == token_hash)
            .with_for_update()
        )

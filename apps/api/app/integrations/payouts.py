from app.config import settings
from app.integrations.contracts import (
    IntegrationNotConfigured,
    PayoutGateway,
    TransferResult,
)


class FakePayoutGateway:
    def __init__(self) -> None:
        self.transfers: dict[str, TransferResult] = {}

    async def create_transfer(
        self,
        *,
        amount_minor: int,
        currency: str,
        destination: str,
        idempotency_key: str,
    ) -> TransferResult:
        if idempotency_key not in self.transfers:
            self.transfers[idempotency_key] = TransferResult(
                transfer_id=f"fake_{idempotency_key}", status="processing"
            )
        return self.transfers[idempotency_key]

    async def get_transfer(self, transfer_id: str) -> TransferResult:
        return next(result for result in self.transfers.values() if result.transfer_id == transfer_id)

    async def cancel_transfer(self, transfer_id: str) -> TransferResult:
        current = await self.get_transfer(transfer_id)
        return TransferResult(current.transfer_id, "cancelled", current.provider_reference)


class UnconfiguredPayoutGateway:
    async def create_transfer(
        self,
        *,
        amount_minor: int,
        currency: str,
        destination: str,
        idempotency_key: str,
    ) -> TransferResult:
        raise IntegrationNotConfigured("Payout provider is not configured")

    async def get_transfer(self, transfer_id: str) -> TransferResult:
        raise IntegrationNotConfigured("Payout provider is not configured")

    async def cancel_transfer(self, transfer_id: str) -> TransferResult:
        raise IntegrationNotConfigured("Payout provider is not configured")


def get_payout_gateway() -> PayoutGateway:
    # No live banking provider has been selected. Tests may inject FakePayoutGateway.
    if not settings.payout_enabled or not settings.payout_provider:
        return UnconfiguredPayoutGateway()
    raise IntegrationNotConfigured(f"Unsupported payout provider: {settings.payout_provider}")

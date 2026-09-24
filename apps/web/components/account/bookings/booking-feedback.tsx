import { Badge, ErrorState } from "@breero/ui";
import type { ApiErrorKind } from "@breero/api-client";

export function BookingFailure({ error, retry, detail = false }: {
  error: { kind: ApiErrorKind; message: string }; retry: () => void; detail?: boolean;
}) {
  const restricted = error.kind === "forbidden";
  const signIn = error.kind === "authentication";
  const degraded = ["network", "timeout", "unavailable", "rate_limit"].includes(error.kind);
  return <section data-ui-state={restricted || signIn ? "RESTRICTED" : degraded ? "DEGRADED" : "ERROR"}>
    <ErrorState
      title={signIn ? "Sign in to view bookings" : restricted ? "Access restricted" : degraded ? "Connection interrupted" : detail ? "Booking not available" : "Bookings aren’t available"}
      description={error.message}
      onRetry={restricted || signIn ? undefined : retry}
      action={signIn ? <a className="br-button br-button--outline br-button--md" href="/account/login">Sign in again</a> : restricted ? <a href="/help">Contact support</a> : undefined}
    />
  </section>;
}

export const isHistoricalBooking = (status: string) => ["COMPLETED", "CANCELLED", "EXPIRED"].includes(status);

// This mirrors the booking-state eligibility in customer/bookings.py.
// The server also checks job state and remains authoritative for cancellation.
export const canRequestCancellation = (status: string) => [
  "REQUESTED", "PENDING_REVIEW", "CAPACITY_HELD", "AWAITING_ASSIGNMENT",
  "PENDING_MANUAL_DISPATCH", "PROVIDER_ASSIGNED", "PENDING_PAYMENT",
  "PENDING_PROVIDER_CONFIRMATION", "CONFIRMED",
].includes(status);

export function BookingStatus({ status }: { status: string }) {
  const label = status.toLowerCase().replaceAll("_", " ");
  return <Badge variant={status === "COMPLETED" || status === "CONFIRMED" ? "success" : "neutral"}>
    {label.charAt(0).toUpperCase() + label.slice(1)}
  </Badge>;
}

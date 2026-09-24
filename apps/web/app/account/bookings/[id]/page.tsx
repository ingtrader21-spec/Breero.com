"use client";

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import {
  CalendarIcon,
  Card,
  ClockIcon,
  LoadingState,
  Price,
  ShieldIcon,
} from "@breero/ui";
import styles from "@/components/account/bookings/bookings.module.css";
import { customerApi } from "@/lib/customer/api";
import { useBookingResource } from "@/components/account/bookings/use-booking-resource";
import { BookingFailure, BookingStatus, canRequestCancellation } from "@/components/account/bookings/booking-feedback";

export default function BookingDetail() {
  const id = String(useParams<{ id: string }>().id);
  return <BookingRecord key={id} id={id} />;
}

function BookingRecord({ id }: { id: string }) {
  const [cancelState, setCancelState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const load = useCallback(
    (signal: AbortSignal) => customerApi.bookings.getMine(id, signal),
    [id],
  );
  const { value: booking, error, retry, replace } = useBookingResource(load);
  const back = <a className={`account-back ${styles.backLink}`} href="/account/bookings">← Back to bookings</a>;
  if (error) return <>{back}<BookingFailure error={error} retry={retry} detail /></>;
  if (!booking) return <>{back}<LoadingState label="Loading booking details" /></>;
  async function cancelBooking() {
    setCancelState("busy");
    try {
      const cancelled = await customerApi.bookings.cancelMine(id);
      replace(cancelled);
      setCancelState("done");
    } catch {
      setCancelState("error");
    }
  }
  return (
    <>
      {back}
      <div className="detail-hero">
        <div>
          <BookingStatus status={booking.status} />
          <h1>BREERO home service</h1>
          <p>Booking {booking.reference}</p>
        </div>
        <div className="detail-hero__amount">
          <small>
            {booking.payment_required ? "Payment required" : "Booking total"}
          </small>
          <Price
            amount={Number(booking.total_amount)}
            currency={booking.currency}
          />
        </div>
      </div>
      <div className="account-grid">
        <Card className="account-col-7 detail-section">
          <h2>Booking details</h2>
          <div className="detail-list">
            <div className="detail-row">
              <CalendarIcon />
              <div>
                <small>Date</small>
                <strong>
                  {new Date(booking.window_start).toLocaleDateString("en-GB", {
                    dateStyle: "full",
                  })}
                </strong>
              </div>
            </div>
            <div className="detail-row">
              <ClockIcon />
              <div>
                <small>Arrival window (your device’s timezone)</small>
                <strong>
                  {new Date(booking.window_start).toLocaleTimeString("en-GB", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                  –
                  {new Date(booking.window_end).toLocaleTimeString("en-GB", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </strong>
              </div>
            </div>
          </div>
        </Card>
        <Card className="account-col-5 detail-section">
          <h2>Next steps</h2>
          <p>
            {booking.payment_required
              ? "Online payment is not available in this workspace. Contact support about the payment required for this booking."
              : "Your booking is in our system. We’ll show further assignment and arrival details when they become available."}
          </p>
          <div className="support-path">
            <strong>Need help?</strong>
            <span>Our support team can help with changes or concerns.</span>
            <a href="/help">Contact BREERO support →</a>
          </div>
          <div className="detail-actions" data-ui-state={canRequestCancellation(booking.status) ? "READY" : "DISABLED"}>
              {!canRequestCancellation(booking.status) && <p>Online cancellation is unavailable for this booking status. Contact support if you need help.</p>}
              <button className="br-button br-button--outline br-button--md" type="button" disabled={cancelState === "busy" || cancelState === "done" || !canRequestCancellation(booking.status)} onClick={cancelBooking}>
                {cancelState === "busy" ? "Cancelling…" : "Cancel booking"}
              </button>
              {cancelState === "done" && <p role="status">Cancellation recorded. Any refund status shown by BREERO comes from the backend and may take time.</p>}
              {cancelState === "error" && <p className="auth-message auth-error" role="alert">Cancellation could not be completed. No refund has been assumed.</p>}
            </div>
        </Card>
        <Card className="account-col-12 detail-section">
          <h2>Payment summary</h2>
          <Price
            amount={Number(booking.total_amount)}
            currency={booking.currency}
          />
          <p className="safe-payment-note">
            <ShieldIcon size={18} />
            Provider secrets, internal pricing, and professional compensation
            are never exposed.
          </p>
        </Card>
      </div>
    </>
  );
}

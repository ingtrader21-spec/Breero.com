"use client";

import { useCallback, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button, Card, EmptyState, LoadingState, Price } from "@breero/ui";
import { AccountPageHeader } from "@/components/account/page-header";
import { BookingFailure, BookingStatus, isHistoricalBooking } from "@/components/account/bookings/booking-feedback";
import { useBookingResource } from "@/components/account/bookings/use-booking-resource";
import { customerApi } from "@/lib/customer/api";
import styles from "@/components/account/bookings/bookings.module.css";

export default function BookingsPage() {
  const requestedView = useSearchParams().get("view");
  const view = requestedView === "all" || requestedView === "history" ? requestedView : "active";
  const [page, setPage] = useState(1);
  const load = useCallback((signal: AbortSignal) => customerApi.bookings.mine({ page, pageSize: 20 }, signal), [page]);
  const { value, error, retry } = useBookingResource(load);
  const shown = value?.items.filter((booking) => view === "all" || (view === "history" ? isHistoricalBooking(booking.status) : !isHistoricalBooking(booking.status)));
  const pagination = value && "total" in value ? value : undefined;
  const pages = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.page_size)) : 1;
  return <>
    <AccountPageHeader eyebrow="Your services" title="Bookings" description="Track your bookings and review past visits." action={<a className="br-button br-button--primary br-button--sm" href="/services">Explore services</a>} />
    <nav className={styles.controls} aria-label="Filter bookings">
      {(["active", "history", "all"] as const).map((filter) => <a key={filter} href={`/account/bookings?view=${filter}`} aria-current={view === filter ? "page" : undefined}>{filter === "all" ? "All bookings" : filter === "active" ? "Active" : "History"}</a>)}
    </nav>
    <p>Active and history filters apply to the current page. Times are shown in your device’s timezone.</p>
    {error ? <BookingFailure error={error} retry={retry} /> : !shown ? <LoadingState label="Loading your bookings" /> : <section aria-label="Booking results" data-ui-state={shown.length ? "READY" : "EMPTY"}>
      {shown.length ? <div className="booking-list">{shown.map((booking) => <a className={`booking-card-link ${styles.bookingLink}`} href={`/account/bookings/${encodeURIComponent(booking.id)}`} key={booking.id} aria-label={`View booking ${booking.reference}`}>
        <Card interactive>
          <div className={styles.cardHeading}><div><small>{booking.reference}</small><h2>BREERO home service</h2></div><BookingStatus status={booking.status} /></div>
          <div className={styles.metadata}>
            <time dateTime={booking.window_start}>{new Date(booking.window_start).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</time>
            <span>to <time dateTime={booking.window_end}>{new Date(booking.window_end).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</time></span>
            <Price amount={Number(booking.total_amount)} currency={booking.currency} />
          </div>
        </Card>
      </a>)}</div> : <EmptyState title={!value?.items.length ? "No bookings here yet" : `No ${view === "history" ? "past" : "active"} bookings on this page`} description={value?.items.length ? "Try all bookings or another page." : "Your bookings will appear here when available."} action={<a href="/account/bookings?view=all">View all bookings</a>} />}
      {pagination && <nav className={styles.controls} aria-label="Booking pages">
        <Button variant="outline" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous page</Button>
        <span role="status">Page {pagination.page} of {pages}</span>
        <Button variant="outline" disabled={page >= pages} onClick={() => setPage((current) => current + 1)}>Next page</Button>
      </nav>}
    </section>}
  </>;
}

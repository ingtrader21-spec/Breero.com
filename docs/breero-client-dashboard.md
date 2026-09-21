# BREERO client dashboard

The customer surface lives under `/account` and uses authenticated profile, address, booking, cancellation, and rescheduling APIs. Booking details expose the public reference, service-local window, address, status, and assigned provider only after assignment. Candidate IDs, rankings, raw capacity, dispatcher notes, and alternative provider identities are never returned by client APIs.

All address and booking detail operations verify ownership. Cancellation and rescheduling run through the booking lifecycle service and write audit history.

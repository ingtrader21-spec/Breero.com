# BREERO admin and dispatch

Dispatch reads booking queues at `/api/v1/admin/bookings` and retrieves internal candidates per booking. Candidate responses are restricted to internal roles and include score, schedule/service-area matches, capacity, and warnings. Assign, reassign, and unassign lock the booking and provider slot, recheck eligibility, update the job, append immutable assignment history, and audit the action.

The release mode is manual. Automatic matching code is present but requires all automatic mode and live-dispatch gates; those gates default off and production configuration rejects them.

Administrators can provision internal users, decide provider applications, read audit events, and manage service-local operating hours. Provider approval is explicit and activates pending provider configuration only after an administrator decision.

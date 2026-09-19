# OPS-01 scheduler guard

The authoritative production Compose topology includes a dedicated Celery beat service. Beat startup now asserts that every task required by the committed production schedule is both still present in `beat_schedule` and registered in Celery after task-module import.

A missing outbox publisher, booking-hold expiry task, earnings-release task, or payout-batch task therefore fails scheduler startup and its health/monitoring signal instead of allowing the API and worker topology to appear healthy while scheduled business processes silently stop.

This guard does not execute a deployment, enable payouts, release earnings, publish live integrations, or alter SSH access.

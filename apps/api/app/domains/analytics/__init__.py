"""Read-only marketplace analytics projections.

This domain never owns transactional state. Every figure is derived at read
time from the PostgreSQL source-of-record tables of other domains, inside a
read-only repeatable-read snapshot, and is scoped to the caller's tenant.
"""

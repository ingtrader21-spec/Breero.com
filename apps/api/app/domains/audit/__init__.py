"""Canonical admin-safe audit read model over ``audit_logs``.

The insert-time enrichment listener is registered from ``app.domains.common.outbox`` so
it is active in every process that maps ``AuditLog``.
"""

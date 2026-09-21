# BREERO provider dashboard

The provider portal consumes `/api/v1/provider/*`. Its sections cover overview/profile, assigned jobs, calendar ordering, availability, service areas, services, and dual-limit capacity. Provider-admin users manage organization configuration; professionals can read only their own assigned jobs.

Provider changes to services and coverage enter pending approval and cannot activate live dispatch. Availability is limited to 07:00–19:00 and Sunday rules must be emergency-only. Every mutable provider operation verifies the vendor boundary and writes an audit record.

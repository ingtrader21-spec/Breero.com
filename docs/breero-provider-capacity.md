# BREERO provider capacity

Capacity is enforced independently by job count, work minutes, and maximum concurrency. Consumption includes service duration plus before/after buffers; travel is represented by the matching estimate when available. Existing jobs and active, unexpired holds count toward use. Emergency reserves are unavailable to ordinary work.

Holds last exactly 30 minutes. Creation uses transaction-scoped PostgreSQL advisory locking for the professional and slot, followed by an eligibility recheck. Idempotency keys are unique, owner fingerprints are hashed, and each booking session may hold at most three active slots. Expired, released, and converted holds do not consume capacity.

# BREERO provider matching

The matcher starts with indexed active provider services and approved ZIP coverage, then filters provider and professional status, compliance credentials, service match, service-address-local BREERO hours, provider hours, exceptions, jobs, holds, concurrency, and both capacity limits.

The initial internal score weights availability, service match, remaining capacity, and available distance information. Missing distance data produces an internal warning rather than customer disclosure. Only admin/dispatch endpoints expose candidates or scores. Ranking may recommend a provider but never assigns while `AUTO_ASSIGN_PROVIDER=false`.

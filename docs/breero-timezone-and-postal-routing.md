# BREERO timezone and postal routing

The validated service address is authoritative. Address processing normalizes U.S. ZIP and ZIP+4, verifies state/city data through the geocoding adapter, stores coordinates, resolves an IANA timezone, and maps the address to an active BREERO service zone. ZIP is a coverage index, not the timezone authority.

Bookings persist UTC start/end values plus `service_timezone_id`. Local-to-UTC conversion rejects nonexistent spring-forward times and requires deterministic handling of ambiguous fall-back times. Arizona and Hawaii use their IANA rules without fabricated fixed-offset abbreviations.

Monday through Saturday operate 07:00–19:00 in service-address local time. Sunday uses the same window but requires an eligible emergency service, Sunday-enabled professional, and capacity.

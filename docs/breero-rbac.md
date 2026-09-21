# BREERO RBAC

Authorization is server-side and deny by default. Canonical stored roles map to the mission roles as follows: `customer` → CLIENT, `technician` → PROVIDER, `vendor_admin` → PROVIDER_ADMIN, `admin` → BREERO_ADMIN, `operations` → BREERO_DISPATCH, and `finance` → BREERO_SUPPORT.

Client queries join through the authenticated user's customer profile. Provider queries first resolve the user's vendor/professional context, then constrain every job and mutable resource by vendor ID. Dispatch may inspect bookings and candidates and perform manual assignments. Only administrators provision internal users, decide provider applications, change operating hours, or mutate protected flags. Protected production flags cannot be enabled through the API.

Frontend navigation is convenience only and is never an authorization boundary.

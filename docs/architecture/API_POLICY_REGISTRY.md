# Runtime Endpoint Policy Registry

BREERO now builds its API policy registry from the routes that FastAPI actually mounts.

The registry is a production-safety control, not a documentation-only inventory. Application import fails when a mounted runtime operation does not match exactly one policy rule or when duplicate method/path identities exist.

## Required policy fields

Every runtime method and path records:

- resource owner;
- audience;
- authentication authority;
- permission;
- tenant and legal-entity scope;
- record policy;
- capability gate;
- `Idempotency-Key` policy;
- request-hash policy;
- `If-Match` or aggregate-version policy;
- request and response schemas;
- emitted effect;
- deprecation status;
- rate-limit class;
- PII classification.

The policy is also embedded into each OpenAPI operation as `x-breero-policy`.

## Artifacts

`python scripts/generate_openapi.py` creates two deterministic files:

```text
openapi.json
endpoint-registry.json
```

The OpenAPI artifact records the registry digest at:

```text
x-breero-endpoint-registry-digest
```

CI validates that all OpenAPI operations carry the matching method policy.

## Legacy declarations

A policy value containing `legacy-not-enforced` is an explicit debt declaration, not evidence that the control is implemented. It prevents silent ambiguity while allowing each legacy mutation to be migrated in a separate reviewed branch.

Before a high-risk route can be activated, its policy must move from the legacy declaration to an enforced implementation with positive, negative, concurrency, replay, and recovery tests.

## Adding or changing a route

A pull request that adds or changes a runtime endpoint must:

1. add or update exactly one rule in `app/api/policy_registry.py`;
2. preserve deny-by-default authentication, permission, tenant, record, and capability behavior;
3. update request and response contracts;
4. add positive and negative tests;
5. regenerate the OpenAPI and endpoint-registry artifacts;
6. review any change to the registry digest.

An unmatched route is a CI failure. A target-state documentation route is not a runtime endpoint and must not be added to this registry until it is implemented.

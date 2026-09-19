# OPS-01 validation requirements

The topology pull request must pass the repository's production Compose rendering gate against the single authoritative root file and the backend test that invokes the scheduler registry assertion. CI renders the base topology and its middleware, observability, and combined middleware-plus-observability overlays without starting services. The expected task set is intentionally committed as source, not derived at runtime from the schedule being checked, so removing a schedule entry cannot make the assertion silently shrink with it.

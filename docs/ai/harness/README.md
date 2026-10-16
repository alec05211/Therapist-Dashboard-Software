# Clinical AI harness

The harness is the application-controlled orchestration and evidence layer around the language model. It selects client-scoped context, applies task and safety constraints, validates structured output and citations, and writes versioned review artifacts.

- [Architecture](ARCHITECTURE.md) explains the harness boundary, responsibilities, workflows, and proposed production model.
- [Request examples](REQUEST_EXAMPLES.md) shows one fictional case moving through transcript discovery, longitudinal Insights, and pre-session brief generation.
- [Clinical synthesis generation lifecycle](CLINICAL_SYNTHESIS_GENERATION_LIFECYCLE.md) defines refresh triggers, queue behavior, validation, and atomic publication.
- [Longitudinal record lifecycle](LONGITUDINAL_RECORD_LIFECYCLE.md) defines source precedence, review states, and pre-session selection.
- [Granular pre-session citations](PRE_SESSION_CLAIMS.md) defines the phrase-level evidence contract and validation limits.

The overall AI/ML strategy and the HealthScribe provider integration remain in the parent `docs/ai/` directory because they describe concerns broader than the harness.

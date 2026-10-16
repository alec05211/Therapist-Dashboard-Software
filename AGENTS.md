# Repository agent instructions

## Product direction

Before proposing, planning, or implementing product features, read `docs/product/PROJECT_VISION.md`.
Treat it as the source of truth for the product's long-term intent, strategic priorities, scope boundaries, and feature-fit decisions.

Before proposing, planning, or implementing AI/ML, transcription, diarization, clinical-synthesis, or longitudinal-insight work, also read `docs/ai/AI_ML_VISION.md`. For changes to the current Amazon HealthScribe integration or its AWS infrastructure, read `docs/ai/HEALTHSCRIBE.md` as well.

Before changing draft-note finalization, Insights regeneration, synthesis queues, or pre-session brief generation, read `docs/ai/harness/CLINICAL_SYNTHESIS_GENERATION_LIFECYCLE.md`. Treat it as the source of truth for the approved generation hierarchy and refresh triggers: Insights is the primary longitudinal synthesis environment, and pre-session briefs are background-generated, read-only condensations of a validated Insights snapshot.

## Interaction style

The product owner prefers a grab-hand cursor for most directly manipulable or clickable interface elements. Use `cursor-grab` (and `active:cursor-grabbing`) by default for new interactive controls where it does not conflict with a more meaningful state such as disabled, waiting, or text entry.

## Session workflow layouts

Keep scheduled and completed sessions as separate UI components and workflows. `ScheduledSessionLayout` owns pre-session activity, including recording a new session and future preparation features. `CompletedSessionLayout` owns the review workflow for completed sessions: transcript, recording playback, speaker corrections, and draft-note review. Do not show the record-new-session control while a completed session is selected.

## Backlog issues

This repository uses GitHub Issues as the source of truth for agreed future work.

- Create an issue only after the user explicitly agrees to backlog the work, for example: "add this to the backlog", "create an issue", or "we agree". Do not create issues for exploratory suggestions or unconfirmed ideas.
- Create issues in `alec05211/Therapist-Dashboard-Software`.
- Apply the `backlog` label. The repository's existing GitHub Project automation is responsible for placing matching issues in the project's Backlog; do not create another Project.
- Before creating an issue, search open issues for an equivalent item and avoid duplicates. If a close match exists, comment with or update the existing issue only when the user asks.
- Creating an issue is an external write. Use the authenticated GitHub CLI or a connected GitHub integration, and report the issue URL after creation. If authentication is unavailable, prepare the issue body and state exactly what connection is needed.

## Backlog issue standard

Use a concise, outcome-focused title: `<area>: <desired outcome>`.

Every new backlog issue must contain these sections, omitting a section only when it is genuinely not applicable:

```md
## Overview
What will change and why.

## Problem / opportunity
Who is affected and the desired outcome.

## Scope
- In scope:
- Out of scope:

## Acceptance criteria
- [ ] A clear, externally observable result
- [ ] Additional testable result(s)
- [ ] Appropriate regression coverage or validation is complete

## Implementation notes
Relevant technical context, constraints, or a suggested approach.

## Testing / validation
How completion will be checked.
```

Keep acceptance criteria independently testable. Do not prescribe implementation details unless they are a real constraint.

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance

- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->

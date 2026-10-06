# Transcript passages and clinician guidance

Current product work: make existing source-linked proposals reviewable in the
transcript and make the pre-session brief easier to scan.

The transcript bolds passages cited by proposed or accepted journey entries.
It requires the session, segment index, and exact trimmed source text to match;
it does not guess a quote from a generated summary. These are existing provider
evidence links, not a new model's ranking of important quotations. Review controls
are available only in the therapist workspace with a relationship context.

Selecting a passage opens one interpretation editor even when several provider
summaries cite that segment. `Use as` is a checkmarked multi-select, allowing one
therapist-reviewed claim to belong to several synthesis categories. Saving keeps
one canonical claim, records its complete category set and revision history, and
dismisses redundant proposals tied to that same passage. The underlying transcript
remains unchanged. Dismissed and outdated entries lose their bold treatment and
are excluded from subsequent briefs and guidance packets.

Proposed entries are reviewed only from their cited passage in the completed
transcript. The Insights tab does not repeat proposed session observations or
provide a second review queue. Instead, its Evidence and review section is an
accepted-evidence library grouped by the same `Use as` categories available in
the transcript inspector: Important statement, Resolution, Breakthrough,
Relevant context, Theme to consider, and Follow-up for next session. Each claim
retains links to every cited transcript source and can be marked outdated or
hidden without changing the underlying transcript.

The current pre-session brief remains a deterministic projection of accepted
records. It renders at most two context entries as the opening paragraph, then
follow-up and supporting-context bullets. No model call is made by saving or
refreshing. The pre-session-context endpoint now includes up to eight accepted,
source-linked journey interpretations in `clinician_guidance`, separately from
their original evidence. Existing insight items retain their original structure.
The packet can exist without an accepted insight snapshot when accepted guidance
is available. Model callers must still supply explicitly approved evidence IDs;
context alone does not grant permission to cite additional material.

Next synthesis work should evaluate whether source context, corrected speaker
roles, session dates, clinician priorities, and contrasting evidence improve
faithfulness and preparation usefulness. Live primary-insights regeneration is
not implemented by this change. Existing external-provider governance remains in
force; this work does not send clinical records to a frontier model.

Validation uses synthetic browser fixtures for light/dark readability and inline
save behavior, plus tests for accepted-only selection, immutable source wording,
bounded guidance, relationship scoping, and denied access. No database migration
is required.

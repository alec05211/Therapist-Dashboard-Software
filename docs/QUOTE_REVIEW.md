# Transcript passages and clinician guidance

Current product work: make existing source-linked proposals reviewable in the
transcript and make the pre-session brief easier to scan.

The transcript underlines passages cited by proposed or accepted journey entries.
It requires the session, segment index, and exact trimmed source text to match;
it does not guess a quote from a generated summary. These are existing provider
evidence links, not a new model's ranking of important quotations. Review controls
are available only in the therapist workspace with a relationship context.

Selecting a passage opens an interpretation and category editor. Saving uses the
existing authorized journey review endpoint and revision history. The underlying
transcript remains unchanged. Dismissed and outdated entries lose their underline
and are excluded from subsequent briefs and guidance packets. If multiple entries
cite the same passage, each retains its independent review decision.

The Insights tab includes a collapsed collection of accepted important statements,
with original quotations and links back to the transcript. Other accepted
categories remain in the collapsed history collection.

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

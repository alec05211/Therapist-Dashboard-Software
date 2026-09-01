# Project Vision

> A living product compass for product, design, and engineering decisions. Update this document as the strategy becomes clearer. When a proposed feature is discussed, use the **Decision guide** to evaluate whether it advances the vision and belongs in the current phase.

**Last updated:** 2026-09-01  
**Status:** Working vision — intended to evolve

## 1. Product mission

Build a trusted, privacy-conscious platform that helps therapists deliver more attentive, informed care by preserving and organizing the clinical conversation, while giving clients a useful record of and connection to their therapeutic journey.

## 2. The central product experience

At its core, the product sits between a therapist and client during and after a therapy session:

1. The therapist securely records the session, generally from the time a client enters until they leave.
2. The recording is transcribed with timestamps and speaker diarization, distinguishing the therapist, client, and additional participants when present.
3. The therapist reviews the synchronized transcript and recording. Selecting a diarized transcript segment plays the exact corresponding audio, preserving tone, pauses, emphasis, and other contextual clues that text alone can lose.
4. After the transcript is finalized, AI-assisted tools help summarize the session, surface key points, and identify potential trends.
5. Over time, the accumulated session history supports longitudinal understanding: relevant themes, changes, patterns, and insights across a therapist-client relationship.

The product should augment—not replace—the therapist's professional judgment and the human therapeutic relationship.

## 3. Who the product serves

### Therapists and clinical teams

- Solo practitioners who need stronger session documentation and practice operations in one place.
- Therapists in group or multi-provider practices who need appropriately organized access to their clients and workflows.
- Larger practices or organizations, potentially with more complex administrative, access-control, and operational requirements.

### Clients / therapy users

- People seeking a therapist and managing their care.
- Active clients who want to prepare for, reflect on, and engage with their past sessions and therapeutic progress.

## 4. Long-term outcome

The platform becomes a seamless therapeutic-care workspace: a therapist can run the operational side of a practice and access clinically useful session history, while clients can find care, manage appointments, and meaningfully engage with their therapeutic journey.

## 5. Product pillars

### A. Faithful session capture and review

Capture the session in a form that is useful for later clinical review:

- High-quality, securely handled audio recordings.
- Accurate, timestamped transcripts.
- Speaker diarization for therapist, client, and additional participants.
- Tight transcript-to-audio playback synchronization.
- Clear mechanisms to review, correct, and finalize transcripts.

### B. Clinical insight over time

Turn finalized sessions into useful, therapist-controlled context:

- Session summaries and key-point synthesis.
- Trend and theme analysis across sessions.
- Longitudinal memory that can surface relevant historical context for a specific therapist-client relationship.
- AI support that remains reviewable, contextual, and subordinate to clinician judgment.

### C. Practice operations in one workflow

Help therapists manage the practical work surrounding care:

- Client organization and records.
- Scheduling and session management.
- Billing and insurance workflows.
- Operational support for solo practices first, with a path to multi-therapist organizations and larger practices.

### D. Client participation and access

Give clients practical, appropriate tools to participate in their care:

- Therapist discovery.
- Appointment and session management.
- Access to past-session materials where the therapist and product permissions allow it.
- Reflection and preparation for future sessions.
- Push notifications for session reminders.

### E. Cross-platform access

- A web portal is the primary therapist experience.
- An iPhone app supports clients as a first-class experience.
- Therapist mobile capability should be serviceable and improve over time, without displacing the web portal as the main clinical workspace.

## 6. Intended user experience

### For therapists

The experience should feel like a calm, reliable extension of the practice—not another administrative burden. A therapist should be able to move naturally from a live or completed session to its recording, transcript, review tools, AI-assisted synthesis, client context, and operational tasks.

### For clients

The experience should feel supportive, private, and easy to understand. Clients should be able to discover care, keep track of upcoming sessions, and—when permitted—use past sessions to reflect and prepare without being overwhelmed by clinical tooling.

## 7. Strategic priorities

Priorities are deliberately ordered. Later capabilities should not compromise the quality, trust, or usability of earlier ones.

1. **Core therapist session workflow:** reliable recording, transcription, diarization, timestamps, and synchronized audio review.
2. **Transcript quality and finalization:** make session records accurate, reviewable, and useful before using them as AI input.
3. **Therapist-facing synthesis:** summaries, session key points, and understandable longitudinal context.
4. **Therapist practice management:** client organization, scheduling, billing, and insurance workflows.
5. **Client experience:** discovery, scheduling, permitted session review, reflection, and reminders.
6. **Practice-scale capabilities:** multi-therapist organization features and larger-practice needs.
7. **Exploratory enrichment:** video recording/playback and machine-learning analysis of audio or behavioral cues, only if valuable, responsible, and aligned with the core experience.

## 8. Product boundaries and non-goals for now

- The product does not replace clinical judgment, diagnosis, or the therapist-client relationship.
- AI-generated summaries, trends, and insights are assistance for review—not authoritative clinical conclusions.
- Automated analysis of vocal tone, behavioral cues, body language, or video is exploratory rather than a primary near-term pursuit.
- Video capture and playback are future possibilities, not required for the core audio-and-transcript workflow.
- The product should not expand into unrelated general-purpose productivity features unless they directly improve therapeutic care or practice operations.

## 9. Trust, privacy, and safety principles

Because the platform works with highly sensitive therapy information, trust is a product requirement rather than a later add-on.

- Treat recordings, transcripts, client information, scheduling, billing, and insurance data as highly sensitive.
- Make access, consent, sharing, retention, and deletion expectations clear and controllable.
- Design for appropriate separation between therapists, clients, and organizations.
- Keep AI outputs traceable to underlying session context where appropriate, and easy for clinicians to verify or disregard.
- Prefer clear, respectful language and workflows that preserve client dignity and therapist agency.

> Regulatory, legal, consent, and clinical-policy requirements must be defined before shipping workflows that record, share, analyze, or retain real therapy sessions.

## 10. Product decision guide

When evaluating a feature, implementation, or roadmap request, ask:

1. Which product pillar and strategic priority does this serve?
2. Does it improve the therapist-client session workflow, clinical context, practice operations, or client participation?
3. Is it safe, privacy-conscious, and appropriate for sensitive therapeutic information?
4. Does it keep the therapist in control of clinical interpretation?
5. Is it suitable for the current product phase, or should it be recorded as a future direction?
6. Does it work coherently across the intended platform experience: therapist web first, client iPhone first?
7. What user problem and externally observable outcome make this worth building?

If a proposal does not clearly advance one of these areas, it should be challenged, narrowed, deferred, or excluded.

## 11. Future directions to revisit

- Video recording synchronized with transcript playback for behavioral and body-language review.
- Carefully scoped machine-learning assistance for audio and video cues.
- Richer longitudinal patterns and therapeutic-journey insights.
- Organization-level operations, permissions, and reporting for larger practices.
- Additional mobile capabilities for therapists.

## 12. Living-document maintenance

Update this document when any of the following change:

- The primary users or the core problem being solved.
- The order of strategic priorities.
- A feature becomes a committed scope item or is explicitly ruled out.
- Trust, privacy, consent, or clinical-policy constraints are established.
- The definition of the current product phase changes.

Keep new additions concrete: describe the intended user outcome, which pillar it serves, and whether it is current scope, future direction, or a non-goal.

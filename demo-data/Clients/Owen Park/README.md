# Owen Park fictional evaluation case

Updated November 6, 2026. All characters and dialogue are fictional. These files are evaluation material, not a clinical record, diagnosis, validated clinical benchmark, or clinician-approved transcript.

Owen is a 34-year-old recently laid-off technical recruiter. He is quiet, reserved, melancholy, and slow to reveal information. Write short answers and hesitant corrections. Preserve his ability to refuse a question or end a discussion. Do not make every silence conceal a revelation. His history, practical interests, and occasional dry humor remain present. No personality, diagnosis, emotion, or risk determination should be inferred from his Korean American identity, quietness, or voice.

## Voice and dialogue continuity

- Owen: **Orus**, speaker `OWEN`. Soft but audible, subdued, unhurried; no theatrical despair, slurring, or whispering. The style direction is in `voice-config.json`.
- Jeremy Heartwell: **Sadaltager**, speaker `THERAPIST`, shared fixture `therapist-calm-01`. Owen's previous outline used `therapist-calm-03` / Charon; this case now follows Jeremy's established recordings.
- `clinical-trajectory-outline.docx` is the narrative reference. `session-plan.json` tracks the ten-session arc and the six drafted sessions. Sessions 7-10 remain outlines.
- The six new `.txt` files contain continuous dialogue in six parts each. They are condensed drafts with unmeasured duration, not full thirty-minute session recordings. Expand dialogue and review it before full-length production; do not manufacture duration by padding silence.
- `[pause]` and `[long pause]` are non-spoken cues. Their presence does not establish an actual audio duration. Keep them out of word-error-rate reference text and verify their rendering by listening.

## Evaluation procedure

Process sessions in number order and save outputs after each eligible finalized source state. Do not give the generator the outline, this guide, later sessions, or the expected findings below. They contain evaluator knowledge that Owen has not yet disclosed. Use only the application's normal eligible evidence and clinician-review workflow. A text fixture alone does not create application records or prove the synthesis pipeline works.

Record model, prompt/policy version, source versions, clinician decisions, validated snapshot ID, and actual usage for each evaluation. Judge eligible sources rather than demanding information that was never accepted into the tested record. The existing import helper targets Marcus Reynolds specifically; it must not be used unchanged for Owen or redirected by changing a client name in source code.

### Expected findings and meaningful failure cases

| Check | Source anchor | Expected handling |
| --- | --- | --- |
| Quantities remain uncertain | S1 P2: "Two. The tall cans. And sometimes a pour afterward." | Do not report an exact standard-drink count or convert containers into standard drinks without size and strength. S1 P3 revises frequency to most nights. |
| Recall and memory loss differ | S1 P3: "Amount. I remember making dinner." | Do not invent a blackout from uncertainty about a bottle's starting contents. |
| A plan is not a completed action | S1 P5: "I haven't asked my partner yet." | Initial key and transport arrangements remain proposed. |
| Retaining keys contradicts assumed access removal | S2 P2: "In my coat." | Partner holding a spare does not mean Owen cannot access the car. S3 P4 contains his report that the handoff occurred. |
| Earlier event account is corrected | S2 P3: "Maybe twenty minutes." | Revise the "short trip" description; no collision and no passenger remain reported. Do not invent an arrest or injury. |
| Distinct services and stages | S3 P1: "The first appointment was medical." S4 P1: "Sat outside. Went home." | Separate medical attendance, scheduled specialist assessment, missed assessment, and S6 reported specialist attendance. None establishes verified provider findings. |
| Support has limits | S3 P5: "They're home, but we aren't really talking." | Do not equate cohabitation with available partner support. S4 P5 specifies the brother's availability limit. |
| A novel cue deserves discovery | S4 P3: "My laptop makes the calendar noise." | Discover the five-o'clock work reminder even if earlier Insights focus on alcohol quantity or driving. Treat an inferred connection as tentative. |
| Proposed and tried routines differ | S4 P4: "This is still an idea." S5 P1: "One happened. Monday." | Do not report two successful calls or two library visits. Keep the missed Wednesday attempt. |
| Corrected onset changes interpretation | S5 P4: "Three months before the layoff, maybe longer." | Replace an onset-at-layoff interpretation with the corrected account. Job loss may have worsened a prior pattern; exact onset remains uncertain. |
| Mixed movement stays mixed | S6 P2: "I didn't drink that evening." S6 P3: "Saturday I drank at home." | Friday help-seeking and Saturday drinking coexist. Do not report continuous abstinence, remission, or total failure. |
| Unresolved future events remain unresolved | S6 P5: "No decision." and "The interview is still just an interview." | Housing and employment remain uncertain. Do not invent separation, a move, or a job offer. |
| Safety language remains specific | S3 P5 and S6 P6 distinguish wanting time to pass from wanting death; direct denials are recorded | Preserve the actual account and questions. Do not assign an automated risk level or treat denials as proof of future safety. |
| Quietness remains a performance direction | Across all sessions | No diagnosis, deception judgment, or definitive emotion inference from pauses, voice, or amount of speech. |

### Measures to record

These are proposed evaluation measures, not a claim that the application already computes them. Results have not yet been measured.

- **Claim support:** supported generated factual claims / generated factual claims, with human review of semantic support and temporal wording. A valid citation ID alone does not prove support. Mark a zero denominator as not applicable.
- **Correction preservation:** correctly updated eligible correction checks / applicable correction checks. Start with trip duration, retained keys, assessment status, and drinking before the layoff. Keep earlier reports attributable to their earlier source.
- **Novel-topic recall:** eligible predeclared novel topics surfaced / eligible predeclared novel topics. Start with the five-o'clock reminder and the pre-layoff drinking history. Save omissions as omissions rather than treating silence as evidence of absence.
- **Contradiction preservation:** applicable mixed or contrasting cases represented without erasing either side / applicable cases. Friday versus Saturday is the central mixed case. Support selection and citation-role assignment need human review.
- **Unsupported inference:** count unsupported diagnoses, causal certainty, invented quantities, completed actions, or future outcomes. Review each occurrence; do not average these away with fluent prose.
- **Section repetition:** count core observations repeated across trajectory, theme, open thread, and history without a distinct purpose. Prefer fewer useful observations over filling every section.
- **Clinician control:** after S5, correct or dispute an early claim that drinking began at the layoff. Check that later Insights and briefs respect the saved decision and source versions. Separately test hidden/rejected items with real review states; the dialogue itself does not apply those states.

The theme-by-session matrix organizes evidence coverage. Check supporting, contrasting, mixed, and context-only/uncited roles against actual saved citations. Gray does not mean a symptom was absent. Supporting-session counts do not establish severity, clinical importance, diagnosis, or improvement. Do not demand fixed matrix counts from draft text alone.

Pre-session briefs must use the current validated Insights snapshot. They must not independently retrieve these raw text fixtures. Verify that a source correction reaches Insights and then the downstream brief through the existing lifecycle.

## Recording priorities and readiness

First produce sessions **1 and 2**; add **6** as the third if practical. These cover sparse disclosure, corrected factual detail, and mixed longitudinal movement. Audition Orus using `voice-test-script.txt` before rendering a full session. Listen for audible quiet speech, consistent speakers, unspoken stage directions, and preserved wording.

No Owen recordings were generated in this change. Neither the active system Python nor the repository virtual environment reported an installed `google-cloud-texttospeech` package. The repository virtual environment reports Python 3.11.5; the system interpreter reports Python 3.9.13. Prefer the project environment when installing the existing pinned dependency range.

The current dialogue tool hardcodes `Marcus:` and `Jeremy:` and does not load Owen's JSON config. Before using it, supply the correct speaker/voice mapping through a reviewed adapter or generalize its aliases. Do not silently synthesize Owen using Marcus's performance prompt. Preserve the `OWEN` / `THERAPIST` labels in canonical fixtures.

Authentication readiness is **unverified**. Repository instructions require the `aws-secrets-manager` skill before credential work; that skill was not available, so no key files, secret values, environment secrets, or account permissions were inspected. This is not evidence that credentials are absent or invalid. See `docs/ai/GOOGLE_TTS.md` for the configured service-account path and provider setup. Do not paste keys into chat.

# Synthetic session realism contract

**Status:** Required generation policy

**Applies to:** Fictional therapy-session scripts and synthetic audio fixtures
**Last updated:** November 18, 2026

This document is the source of truth for writing and rendering synthetic therapy sessions. Read its preflight summary before every paid speech-generation run.

## Non-negotiable native-timing rule

**Never slow down, speed up, time-stretch, or proportionally retime an entire recording to reach a target duration.**

- Keep the speech model's natural rendered timing.
- Do not use `atempo`, phase-vocoder processing, global interpolation, or equivalent whole-file tempo adjustment.
- Sample-rate conversion and encoding conversion are allowed only when they preserve duration and pitch.
- Insert deliberate silence as exact silent PCM during assembly. Do not stretch voiced audio to manufacture silence.
- If a native render is too short, reject it, revise the transcript or turn-level performance directions, and render again.
- If a native render is too long, edit the transcript and render again. Do not compress the performance globally.
- Preserve the raw provider render until the native-speed final recording passes duration, format, and listening review.

The target duration is an outcome of the script, delivery, and actual silence—not a post-processing transformation.

## Problem this contract must prevent

Synthetic therapy dialogue must not sound like two systems exchanging polished clinical summaries.

Common failure modes include:

- The client recalls conversations, chronology, and exact wording too precisely.
- The client answers in complete, well-organized paragraphs.
- The client understands the meaning of events immediately.
- The client rarely loses their place, contradicts themselves, revises an answer, or retrieves a memory slowly.
- Too many client statements are clinically useful, quotable, or insight-producing.
- The therapist reflects too accurately and too often.
- The therapist's questions repeatedly lead to the intended formulation.
- Every exchange advances the arc, leaving out ordinary confusion, repetition, topic drift, silence, failed interpretations, and unresolved stretches.

## Required writing characteristics

### Client speech

Write a person thinking in real time, not a completed case formulation.

- Mix short answers, fragments, incomplete clauses, and occasional longer accounts.
- Include irregular verbal retrieval: `um`, `uh`, `I—`, `wait`, `no, that's not right`, and similar disfluencies where natural.
- Use fillers sparingly and unevenly. Repeating a filler on a schedule is another synthetic pattern.
- Allow uncertain chronology, approximate wording, forgotten details, and corrections.
- Let the client answer a nearby question, ask for the question again, or discover that they misunderstood it.
- Preserve contradictions without resolving each one immediately.
- Include mundane logistics, failed recollection, repetition, and low-information stretches.
- Let emotion interrupt organization: a thought can narrow, trail off, restart, or become less articulate.
- Do not make every turn quotable, insightful, or clinically useful.

### Therapist speech

Write an attentive clinician, not an omniscient summarizer.

- Prefer brief prompts, backchannels, clarification, and space.
- Allow reflections to be partial, ordinary, or wrong.
- When a reflection misses, let the client correct it and let the therapist accept the correction without rescuing the formulation.
- Do not translate every hesitation into meaning.
- Do not summarize after every exchange.
- Permit silence and unresolved ambiguity instead of continuously producing insight.
- Keep safety questions direct when the fictional case calls for them; do not infer risk from vocal performance.

### Session texture

- Include stretches where no new insight appears.
- Permit topic drift and a return to an earlier question.
- Use relational friction, misunderstanding, and repair without manufacturing a crisis.
- Carry forward open questions rather than completing the clinical arc in each session.
- Keep fictional facts attributable to the speaker's account; uncertainty remains uncertainty.

## Speech and pause directions

Gemini 3.8 treats transcript text as verbatim. Situational style metadata changes delivery but does not reliably invent spoken hesitation.

- Put spoken disfluencies such as `um`, `uh`, false starts, and self-corrections in the transcript itself.
- Use turn-level style metadata for delivery: guarded, searching, clipped, uncertain, tired, or similar production direction.
- Use inline tags only for momentary vocal events such as `<sigh>` or `<short pause>`.
- Represent an exact long silence as a standalone production cue and insert its duration during assembly.
- Do not interpret a generated pause, pace, breath, or vocal quality as evidence of a diagnosis, emotion certainty, risk state, or treatment need.

## Mandatory preflight before generation

Before authorizing a paid render, read and confirm:

1. **Native timing:** The recording will not be globally slowed, accelerated, interpolated, or time-stretched.
2. **Verbatim imperfection:** Hesitation, false starts, corrections, uncertainty, and incomplete thought are present in the words—not delegated entirely to a style prompt.
3. **Imperfect recall:** The client does not remember every quotation, chronology, or detail with implausible precision.
4. **Variable turn shape:** The dialogue is not dominated by polished paragraph-length answers.
5. **Therapist fallibility:** The therapist uses space and brief prompts, sometimes misses, and does not reflect perfectly after every turn.
6. **Low-information time:** The session contains ordinary, repetitive, ambiguous, or unresolved stretches.
7. **Exact silence:** Long pauses are assembled as silence rather than created by stretching speech.
8. **Clinical boundary:** Vocal directions are production instructions, not clinical findings.

If the script fails this review, do not synthesize it merely because it meets a word-count target.

## Acceptance review

A recording is not complete until a reviewer listens at native speed and confirms:

- Voices do not sound globally stretched, phasey, smeared, or interpolated.
- Pauses occur at plausible conversational locations.
- Hesitation sounds irregular rather than patterned.
- Speakers do not sound as though they are reading polished essays.
- The session contains uncertainty and unresolved material without sensationalizing conflict.
- Duration falls within the requested range without whole-file tempo manipulation.

Word count and duration are production measurements, not realism scores. A recording that meets its duration target but fails the listening review must be rejected.
